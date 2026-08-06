"""数据采集层。

基于 Phase 1 实测结论(2026-07-31)适配:
- 东财对 python requests 有 TLS 指纹风控 -> 统一使用 curl_cffi(impersonate="chrome")
- 概念列表: push2 clist 接口, 必须翻页(单页100条, 全量504条)
- 板块成分股: datacenter-web RPT_F10_CORETHEME_BOARDTYPE, filter=NEW_BOARD_CODE="BKxxxx"
- 历史行情: push2his kline 接口 (curl_cffi 可通, akshare/requests 被风控)
- 个股新闻: akshare stock_news_em (唯一可用 akshare 接口, 不依赖 push2)
- 估值/财务: akshare stock_value_em + stock_financial_analysis_indicator
  (原 stock_a_lg_indicator 已移除)
- 所有东财接口必须降频(random 0.8~1.2s) + 指数退避重试
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 移除本机代理, 否则 curl_cffi 也会走代理(实测代理到东财失败)
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

from curl_cffi import requests as creq

from config import (
    BASE_DELAY,
    CONCEPT_PAGE_SIZE,
    EM_CLIST_URL,
    EM_DATACENTER_URL,
    EM_KLINE_URL,
    MAX_CONCEPT_PAGES,
    MAX_RETRIES,
    MAX_REQUEST_INTERVAL,
    MIN_REQUEST_INTERVAL,
    OFFLINE_DIR,
    OFFLINE_FILES,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)

# ============ 数据结构 ============


@dataclass
class StockInfo:
    code: str
    name: str = ""
    price: float = 0.0
    pct_chg: float = 0.0


@dataclass
class News:
    title: str = ""
    content: str = ""
    published_at: str = ""
    source: str = ""
    url: str = ""


@dataclass
class FinancialData:
    pe: float = 0.0
    pb: float = 0.0
    roe: float = 0.0
    pe_percentile: float = 0.5   # PE 历史分位, 0~1, 默认中位
    pb_percentile: float = 0.5
    revenue_growth: Optional[float] = None   # None=无数据
    profit_growth: Optional[float] = None    # None=无数据


@dataclass
class MarketData:
    pct_chg_5d: float = 0.0
    volume_trend: float = 0.0    # 近5日成交量变化(0~1, >0.5 放量)
    volatility: float = 0.0      # 5日波动率
    drawdown: float = 0.0        # 近5日最大回撤(0~1)
    closes: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)


@dataclass
class StockProfile:
    code: str
    name: str
    news: List[News] = field(default_factory=list)
    financials: FinancialData = field(default_factory=FinancialData)
    market: MarketData = field(default_factory=MarketData)
    concepts: List[str] = field(default_factory=list)


# ============ 基础工具: 降频 + 指数退避 ============


class RateLimiter:
    """全局降频器: 保证任意两次东财请求间隔 >= MIN_REQUEST_INTERVAL。"""

    _last_ts: float = 0.0

    @classmethod
    def wait(cls) -> None:
        now = time.time()
        elapsed = now - cls._last_ts
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed + random.uniform(0, 0.1))
        cls._last_ts = time.time()


def get_field_safe(row: Any, candidates: List[str], default: Any = None) -> Any:
    """从行数据中按候选字段名安全取值 (字段变化时自动适配)。

    东财/新浪接口字段名可能变化 (如 "pe" vs "市盈率" vs "PE(TTM)"),
    本函数按候选列表依次尝试, 命中即返回, 全部缺失返回 default。

    参数:
        row: dict / pd.Series / 任意支持 .get 的对象
        candidates: 候选字段名列表 (按优先级)
        default: 全部缺失时的默认值

    返回: 命中字段的值, 或 default。
    """
    if row is None:
        return default
    getter = getattr(row, "get", None)
    for key in candidates:
        if getter is not None:
            val = getter(key)
            if val is not None:
                return val
        else:
            try:
                val = row[key]
                if val is not None:
                    return val
            except (KeyError, IndexError, TypeError):
                continue
    return default


# 财务缓存 (预采集真实数据, 冲刺包 Phase 3)
_FINANCIAL_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _load_financial_cache_entry(symbol: str) -> Optional[Dict[str, Any]]:
    """从 financial_cache.json 读取预采集财务数据。未命中返回 None。

    缓存由 scripts/fetch_financial_data.py 生成 (真实 akshare 数据 + 日期标注)。
    """
    global _FINANCIAL_CACHE
    if _FINANCIAL_CACHE is None:
        path = Path(__file__).resolve().parent.parent / "data" / "financial_cache.json"
        try:
            with open(path, encoding="utf-8") as f:
                _FINANCIAL_CACHE = json.load(f).get("stocks", {})
        except (OSError, json.JSONDecodeError):
            _FINANCIAL_CACHE = {}
    return _FINANCIAL_CACHE.get(symbol)


def _request_with_retry(url: str, params: Optional[Dict] = None, max_retries: int = MAX_RETRIES, **kwargs) -> Optional[Any]:
    """curl_cffi + 指数退避重试。失败返回 None (调用方按默认值处理)。

    max_retries: 重试次数 (行情拉取可传 1 快速失败, 避免限流拖垮演示)。
    """
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        RateLimiter.wait()
        try:
            r = creq.get(url, params=params, timeout=REQUEST_TIMEOUT, impersonate="chrome", **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001 - 采集层吞掉所有异常, 返回默认值
            last_err = e
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
            logger.debug("请求失败(第%d次): %s, %.1fs后重试", attempt + 1, str(e)[:100], delay)
            time.sleep(delay)
    logger.warning("东财接口重试%d次仍失败: %s?%s | %s", MAX_RETRIES, url, params, str(last_err)[:120])
    return None


# ============ 概念板块 ============


def get_concept_list() -> List[Dict[str, str]]:
    """获取东财全量概念板块列表。返回 [{"code": "BKxxxx", "name": "板块名"}, ...]。

    实测要点: 单页固定100条, 必须翻页; 全量约504条。
    策略: 优先读离线包 concept_list.json (Phase 1 已固化全量504条, 板块结构静态),
          离线包缺失/过期才实时拉取。
    失败返回空列表。
    """
    # 1. 优先离线包 (避免每次实时拉触发东财限流)
    offline_path = OFFLINE_DIR / "concept_list.json"
    try:
        if offline_path.exists():
            with open(offline_path, encoding="utf-8") as f:
                mapping = json.load(f)  # {name: code}
            if mapping:
                return [{"code": c, "name": n} for n, c in mapping.items()]
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("离线概念列表加载失败: %s", str(e)[:80])

    # 2. 实时拉取 (离线包缺失时)
    result: List[Dict[str, str]] = []
    for pn in range(1, MAX_CONCEPT_PAGES + 1):
        params = {
            "pn": pn,
            "pz": CONCEPT_PAGE_SIZE,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f12",
            "fs": "m:90+t:3",  # 概念板块
            "fields": "f12,f14",
        }
        data = _request_with_retry(EM_CLIST_URL, params=params)
        if not data:
            break
        diff = (data.get("data") or {}).get("diff") or []
        if not diff:
            break
        for x in diff:
            result.append({"code": x.get("f12", ""), "name": x.get("f14", "")})
        if len(diff) < CONCEPT_PAGE_SIZE:
            break
        time.sleep(random.uniform(MIN_REQUEST_INTERVAL, MAX_REQUEST_INTERVAL))
    return result


def get_concept_stocks(concept_name: str) -> List[StockInfo]:
    """按东财板块名获取成分股。返回统一 StockInfo 列表。失败返回空列表。

    实测要点:
    - 板块名先经 CONCEPT_ALIAS 映射到东财标准名
    - 用 datacenter-web RPT_F10_CORETHEME_BOARDTYPE, filter=NEW_BOARD_CODE="BKxxxx"
      (注意: 必须是 NEW_BOARD_CODE 带 BK 前缀, 不是 BOARD_CODE 数字)
    """
    from config import CONCEPT_ALIAS

    # 1. 概念名 -> 东财标准名 -> 板块 code
    em_name = CONCEPT_ALIAS.get(concept_name, concept_name)
    code = _concept_name_to_code(em_name)
    if not code:
        logger.warning("未找到概念[%s]的板块 code", concept_name)
        return []

    # 2. 通过 datacenter-web 反查成分股
    stocks: List[StockInfo] = []
    page = 1
    while True:
        params = {
            "reportName": "RPT_F10_CORETHEME_BOARDTYPE",
            "columns": "SECURITY_CODE,SECURITY_NAME_ABBR",
            "quoteColumns": "f2~01~SECURITY_CODE~LATEST_PRICE,f3~01~SECURITY_CODE~PCT_CHANGE",
            "pageSize": 200,
            "pageNumber": page,
            "sortTypes": -1,
            "sortColumns": "SECURITY_CODE",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(NEW_BOARD_CODE="{code}")',
        }
        data = _request_with_retry(EM_DATACENTER_URL, params=params)
        if not data or not (data.get("result") or {}).get("data"):
            break
        rows = data["result"]["data"]
        for x in rows:
            try:
                price = float(x.get("LATEST_PRICE") or 0)
                pct = float(x.get("PCT_CHANGE") or 0)
            except (TypeError, ValueError):
                price, pct = 0.0, 0.0
            stocks.append(StockInfo(
                code=str(x.get("SECURITY_CODE", "")),
                name=str(x.get("SECURITY_NAME_ABBR", "") or ""),
                price=price,
                pct_chg=pct,
            ))
        total_pages = (data.get("result") or {}).get("pages", 1)
        if page >= total_pages:
            break
        page += 1
        time.sleep(random.uniform(MIN_REQUEST_INTERVAL, MAX_REQUEST_INTERVAL))

    if not stocks:
        logger.warning("概念[%s](%s) 成分股为空", concept_name, code)
    return stocks


def _concept_name_to_code(name: str) -> str:
    """通过全量概念列表查板块 code。带进程内缓存。失败返回空串。"""
    if not hasattr(_concept_name_to_code, "_cache"):
        cl = get_concept_list()
        _concept_name_to_code._cache = {c["name"]: c["code"] for c in cl}  # type: ignore[attr-defined]
    return _concept_name_to_code._cache.get(name, "")  # type: ignore[attr-defined]


# ============ 个股新闻 (akshare, 唯一可用) ============


def get_stock_news(symbol: str, days: int = 3) -> List[News]:
    """获取个股新闻。akshare stock_news_em(实测不依赖 push2, 可用)。

    实测警告: 返回的最新新闻滞后约1.5个月, 定位为"近期新闻"。
    字段为中文: 新闻标题/新闻内容/发布时间/文章来源/新闻链接。
    失败返回空列表。
    """
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol=symbol)
    except Exception as e:  # noqa: BLE001
        logger.warning("stock_news_em(%s) 失败: %s", symbol, str(e)[:120])
        return []

    if df is None or df.empty:
        return []

    news_list: List[News] = []
    for _, row in df.head(30).iterrows():
        news_list.append(News(
            title=str(get_field_safe(row, ["新闻标题", "标题", "title"], "") or ""),
            content=str(get_field_safe(row, ["新闻内容", "内容", "content"], "") or ""),
            published_at=str(get_field_safe(row, ["发布时间", "时间", "datetime"], "") or ""),
            source=str(get_field_safe(row, ["文章来源", "来源", "source"], "") or ""),
            url=str(get_field_safe(row, ["新闻链接", "链接", "url"], "") or ""),
        ))
    return news_list


# ============ 财务指标 (akshare 替代接口) ============


def get_stock_financials(symbol: str, allow_live: bool = True) -> FinancialData:
    """获取 PE/PB/估值 + ROE。失败返回默认 FinancialData。

    实测要点:
    - stock_a_lg_indicator 已移除 -> 用 stock_value_em(PE/PB/市值)
    - ROE 用 stock_financial_analysis_indicator, 但该接口最新一期可能严重滞后
      (实测停在1997-12-31) -> 拿不到就给默认0, 由离线包/因子层降级处理
    """
    fin = FinancialData()

    # 0. 缓存优先: 预采集的真实财务数据 (fast path, 冲刺包 Phase 3)
    cached = _load_financial_cache_entry(symbol)
    if cached:
        try:
            fin.pe = float(cached.get("pe") or 0)
            fin.pb = float(cached.get("pb") or 0)
            fin.roe = float(cached.get("roe") or 0)
            # 缓存数据可含演示分位; 无分位时保持默认
            if cached.get("pe_percentile"):
                fin.pe_percentile = float(cached["pe_percentile"])
            if cached.get("pb_percentile"):
                fin.pb_percentile = float(cached["pb_percentile"])
            if cached.get("revenue_growth") is not None:
                fin.revenue_growth = float(cached["revenue_growth"])
            if cached.get("profit_growth") is not None:
                fin.profit_growth = float(cached["profit_growth"])
            return fin
        except (TypeError, ValueError):
            pass  # 缓存解析失败, 继续实时拉取

    if not allow_live:
        return fin  # 只读缓存模式: 未命中则不触发实时网络拉取

    try:
        import akshare as ak

        # 1. 估值: stock_value_em
        try:
            df = ak.stock_value_em(symbol=symbol)
            if df is not None and not df.empty:
                row = df.iloc[-1]  # 最新一行
                try:
                    fin.pe = float(get_field_safe(row, ["PE(TTM)", "pe", "市盈率", "市盈率-动态"], 0.0) or 0.0)
                except (TypeError, ValueError):
                    fin.pe = 0.0
                try:
                    fin.pb = float(get_field_safe(row, ["市净率", "pb", "PB"], 0.0) or 0.0)
                except (TypeError, ValueError):
                    fin.pb = 0.0
        except Exception as e:  # noqa: BLE001
            logger.warning("stock_value_em(%s) 失败: %s", symbol, str(e)[:120])

        # 2. ROE: stock_financial_analysis_indicator
        try:
            df2 = ak.stock_financial_analysis_indicator(symbol=symbol)
            if df2 is not None and not df2.empty:
                row = df2.iloc[0]  # 最新一期
                try:
                    fin.roe = float(get_field_safe(
                        row, ["净资产收益率(%)", "净资产收益率", "加权净资产收益率(%)"], 0.0) or 0.0)
                except (TypeError, ValueError):
                    fin.roe = 0.0
        except Exception as e:  # noqa: BLE001
            logger.warning("stock_financial_analysis_indicator(%s) 失败: %s", symbol, str(e)[:120])

    except ImportError:
        logger.warning("akshare 未安装, 财务指标返回默认值")
    return fin


# ============ 历史行情 (curl_cffi 直连 push2his) ============


def get_stock_market_data(symbol: str, days: int = 5) -> MarketData:
    """获取近 N 日行情。curl_cffi 直连 push2his kline 接口。

    实测要点: akshare stock_zh_a_hist 内部用 requests 被东财 TLS 风控,
    必须绕过 akshare 直接用 curl_cffi。
    失败返回默认 MarketData。
    """
    import datetime as _dt

    market = 1 if symbol.startswith("6") else 0
    end = _dt.date.today()
    beg = end - _dt.timedelta(days=days * 2 + 10)

    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "0",
        "secid": f"{market}.{symbol}",
        "beg": beg.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
    }
    data = _request_with_retry(EM_KLINE_URL, params=params, max_retries=1)
    if not data or not (data.get("data") or {}).get("klines"):
        return MarketData()

    klines = data["data"]["klines"][-days:]
    closes: List[float] = []
    volumes: List[float] = []
    for k in klines:
        parts = k.split(",")
        if len(parts) < 6:
            continue
        try:
            closes.append(float(parts[2]))     # 收盘
            volumes.append(float(parts[5]))    # 成交量
        except (TypeError, ValueError):
            continue

    if not closes:
        return MarketData()

    md = MarketData(closes=closes, volumes=volumes)

    # 5日涨跌幅 (首尾收盘对比)
    if len(closes) >= 2:
        md.pct_chg_5d = (closes[-1] - closes[0]) / closes[0] if closes[0] else 0.0

    # 成交量变化: 近2日均值 vs 前段均值, 归一化到 0~1
    if len(volumes) >= 4:
        recent = sum(volumes[-2:]) / 2
        prior = sum(volumes[:-2]) / (len(volumes) - 2)
        if prior > 0:
            md.volume_trend = max(0.0, min(1.0, recent / prior / 2.0))

    # 波动率: 日收益率标准差
    if len(closes) >= 3:
        rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
        if rets:
            mean = sum(rets) / len(rets)
            md.volatility = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5

    # 最大回撤: 峰值到谷值最大跌幅
    peak = closes[0]
    max_dd = 0.0
    for c in closes:
        if c > peak:
            peak = c
        dd = (peak - c) / peak if peak else 0.0
        max_dd = max(max_dd, dd)
    md.drawdown = max_dd

    return md


# ============ 聚合 ============


def get_stock_profile(symbol: str, name: str = "", with_news: bool = True) -> StockProfile:
    """聚合所有数据源, 返回统一 StockProfile。

    各数据源独立容错: 单个失败不影响整体, 失败字段用默认值。
    """
    profile = StockProfile(code=symbol, name=name)
    profile.financials = get_stock_financials(symbol)
    profile.market = get_stock_market_data(symbol)
    if with_news:
        profile.news = get_stock_news(symbol)
    return profile


# ============ 离线包 ============


def load_offline_stocks(topic: str) -> List[StockInfo]:
    """从离线包加载概念成分股 (保底数据源)。失败返回空列表。

    离线包路径由 config.OFFLINE_FILES 映射 (标准名 -> 文件名)。
    """
    fname = OFFLINE_FILES.get(topic)
    if not fname:
        return []
    path = OFFLINE_DIR / fname
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("离线包加载失败 %s: %s", path, str(e)[:100])
        return []

    stocks: List[StockInfo] = []
    for s in data.get("stocks", []):
        try:
            stocks.append(StockInfo(
                code=str(s.get("code", "")),
                name=str(s.get("name", "") or ""),
                price=float(s.get("price") or 0),
                pct_chg=float(s.get("pct_chg") or 0),
            ))
        except (TypeError, ValueError):
            continue
    return stocks


def load_concept_alias_map() -> Dict[str, str]:
    """加载东财概念 code -> 标准名映射 (供事件分析器用)。"""
    from config import CONCEPT_ALIAS

    cl = get_concept_list()
    em_names = {c["code"]: c["name"] for c in cl}
    # 反查: 标准名 -> 东财名 -> code
    alias_reverse = {v: k for k, v in CONCEPT_ALIAS.items()}
    result: Dict[str, str] = {}
    for em_name, code in em_names.items():
        std = alias_reverse.get(em_name, em_name)
        result[code] = std
    return result
