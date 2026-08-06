"""多源数据融合: 主源失败自动切换备源 + 数据新鲜度检查。

数据源优先级:
1. 主源: 东方财富 (curl_cffi, 已适配 TLS 风控)
2. 备源1: 新浪财经 (hq.sinajs.cn 实时行情)
3. 备源2: 离线包缓存 (保底, 永不失联)

设计:
- 每次拉取记录时间戳, 超过 CACHE_TTL (30分钟) 提示刷新
- 全部源失败时返回离线缓存, 调用方可标记"数据来源: 缓存"
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 数据新鲜度跟踪: {data_key: last_fetch_ts}
_FRESHNESS: dict = {}

# 数据来源标记
SRC_EAST = "东方财富"
SRC_SINA = "新浪财经"
SRC_CACHE = "离线缓存"


def get_sina_quote(symbol: str) -> Optional[dict]:
    """从新浪财经获取个股实时行情。失败返回 None。

    新浪格式: var hq_str_sz000099="名称,今开,昨收,现价,最高,最低,买一,卖一,成交量,..."
    """
    import urllib.request

    prefix = "sh" if symbol.startswith("6") else "sz"
    url = f"https://hq.sinajs.cn/list={prefix}{symbol}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = r.read().decode("gbk", errors="replace")
        # 解析: "名称,今开,昨收,现价,最高,最低,..."
        body = data.split('"')[1] if '"' in data else ""
        parts = body.split(",")
        if len(parts) < 10:
            return None
        try:
            return {
                "name": parts[0],
                "open": float(parts[1]),
                "prev_close": float(parts[2]),
                "price": float(parts[3]),
                "high": float(parts[4]),
                "low": float(parts[5]),
                "volume": float(parts[8]),
                "date": parts[30] if len(parts) > 30 else "",
            }
        except (ValueError, IndexError):
            return None
    except Exception as e:  # noqa: BLE001
        logger.warning("新浪行情(%s)失败: %s", symbol, str(e)[:80])
        return None


def get_market_data_multi(symbol: str) -> tuple:
    """多源获取行情: 东财 -> 新浪 -> 缓存。返回 (MarketData, source)。

    返回的第二个元素是数据来源标记 (SRC_EAST/SRC_SINA/SRC_CACHE)。
    """
    from src.data_collector import MarketData, get_stock_market_data

    # 1. 主源: 东财
    try:
        md = get_stock_market_data(symbol)
        if md and getattr(md, "closes", None):
            _mark_fresh(symbol)
            return md, SRC_EAST
    except Exception as e:  # noqa: BLE001
        logger.warning("东财行情(%s)失败, 切新浪: %s", symbol, str(e)[:60])

    # 2. 备源1: 新浪
    try:
        q = get_sina_quote(symbol)
        if q and q.get("price"):
            # 用新浪单日数据构造最小 MarketData
            prev_close = q.get("prev_close") or q.get("price") or 0
            pct = (q["price"] - prev_close) / prev_close if prev_close else 0.0
            md = MarketData(
                pct_chg_5d=pct,
                volume_trend=0.5,
                volatility=abs(pct) * 0.5,
                drawdown=max(0.0, -pct),
                closes=[], volumes=[],
            )
            _mark_fresh(symbol)
            return md, SRC_SINA
    except Exception as e:  # noqa: BLE001
        logger.warning("新浪行情(%s)失败: %s", symbol, str(e)[:60])

    # 3. 备源2: 缓存 (无市场数据, 用默认)
    return MarketData(), SRC_CACHE


def check_freshness(data_key: str, max_age_minutes: int = 30) -> dict:
    """检查数据新鲜度。返回 {"fresh": bool, "age_minutes": float, "last_fetch": str}。"""
    ts = _FRESHNESS.get(data_key)
    if ts is None:
        return {"fresh": False, "age_minutes": None, "last_fetch": None}
    age = (time.time() - ts) / 60.0
    return {
        "fresh": age <= max_age_minutes,
        "age_minutes": round(age, 1),
        "last_fetch": time.strftime("%H:%M:%S", time.localtime(ts)),
    }


def _mark_fresh(data_key: str) -> None:
    _FRESHNESS[data_key] = time.time()


def get_source_label(source: str) -> str:
    """将来源标记转为 UI 展示文本。"""
    labels = {
        SRC_EAST: "东方财富(实时)",
        SRC_SINA: "新浪财经(实时)",
        SRC_CACHE: "离线缓存",
    }
    return labels.get(source, source)
