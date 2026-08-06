"""单资产风险特征分析。
纯规则计算。输出: 风险等级(低/中/高)、波动率、最大回撤、估值风险。
判定规则 (config 中阈值可调):
- 低风险: 波动率<0.20 且 最大回撤<0.15 且 PE分位<0.60
- 中风险: 波动率<0.35 且 最大回撤<0.25
- 高风险: 其余
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

try:
    import akshare as ak
except ImportError:  # akshare 缺失时模块仍可导入, 仅实时 K 线拉取降级
    ak = None

try:
    import numpy as np
except ImportError:
    np = None

from config import (
    RISK_LOW_DRAWDOWN,
    RISK_LOW_PE_PCT,
    RISK_LOW_VOL,
    RISK_MID_DRAWDOWN,
    RISK_MID_VOL,
)

logger = logging.getLogger(__name__)


def _metrics_from_closes(closes) -> Optional[Tuple[float, float]]:
    """从收盘价序列计算年化波动率与最大回撤。数据不足返回 None。"""
    if np is None:
        return None
    values = [float(c) for c in (closes or []) if c]
    if len(values) < 5:
        return None
    arr = np.asarray(values[-20:], dtype=float)
    returns = np.diff(arr) / arr[:-1]
    volatility = float(np.std(returns, ddof=1) * np.sqrt(252))
    peak = np.maximum.accumulate(arr)
    drawdowns = (arr - peak) / peak
    max_drawdown = float(abs(drawdowns.min()))
    return (volatility, max_drawdown)


def _fetch_kline_metrics(code: str) -> Optional[Tuple[float, float]]:
    """从 akshare stock_zh_a_hist 拉取近 20 日 K 线, 计算波动率与最大回撤。
    返回 (volatility, max_drawdown), 拉取失败或数据不足返回 None。
    """
    try:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
        df = ak.stock_zh_a_hist(
            symbol=code, period='daily',
            start_date=start_date, end_date=end_date,
            adjust='qfq',
        )
        if df is None or len(df) < 5:
            logger.warning('K线数据不足 code=%s rows=%s', code, len(df) if df is not None else 0)
            return None

        return _metrics_from_closes(list(df['收盘'].astype(float).values))
    except Exception as e:
        logger.warning('K线拉取失败 code=%s: %s', code, str(e)[:100])
        return None


def analyze_risk(stock: Any) -> Dict[str, Any]:
    """单资产风险特征分析。优先从 akshare K 线计算真实波动率/回撤, 失败返回数据暂缺。
    返回: {
        "risk_level": "低/中/高/数据暂缺",
        "volatility": float,
        "max_drawdown": float,
        "valuation_risk": "低/中/高/数据暂缺",
        "detail": "风险特征描述"
    }
    """
    md = getattr(stock, "market", None)
    fin = getattr(stock, "financials", None)
    code = getattr(stock, "code", "")

    # 注意: 用 if None 而非 or 兜底, 避免 0.0 被误判为缺失 (0.0 or 1.0 == 1.0)
    def _num(val, default):
        return default if val is None else float(val)

    # ---- 从 akshare 拉取近 20 日 K 线, 计算真实波动率和最大回撤 ----
    kline_ok = False
    volatility = _num(getattr(md, "volatility", None), 1.0) if md else 1.0
    drawdown = _num(getattr(md, "drawdown", None), 1.0) if md else 1.0

    if code:
        metrics = _fetch_kline_metrics(code)
        if metrics is not None:
            volatility, drawdown = metrics
            kline_ok = True

    # akshare 拉取失败/不可用: 复用已有行情 (md.closes) 计算真实波动率与回撤
    if code and not kline_ok:
        md_closes = list(getattr(md, "closes", None) or []) if md else []
        if len(md_closes) >= 5:
            metrics = _metrics_from_closes(md_closes)
            if metrics is not None:
                volatility, drawdown = metrics
                kline_ok = True

    # 无任何真实行情 (akshare 失败 + 无 md.closes + 无 md 波动/涨跌) -> 数据暂缺
    md_vol = _num(getattr(md, "volatility", None), 0.0) if md else 0.0
    md_pct5 = _num(getattr(md, "pct_chg_5d", None), 0.0) if md else 0.0
    if code and not kline_ok and not (md_closes or md_vol > 1e-6 or abs(md_pct5) > 1e-6):
        return {
            "risk_level": "数据暂缺",
            "volatility": None,
            "max_drawdown": None,
            "valuation_risk": "数据暂缺",
            "detail": "实时K线与缓存行情均不可用, 无法计算波动率与回撤",
        }

    # 估值分位: 财务缺失时用中性 0.5 (未知 ≈ 高估), 行情也缺失时才是高风险
    # has_market: 有真实行情才算有数据 (closes 非空 或 波动/涨跌非零)
    md_closes = getattr(md, "closes", None) or [] if md else []
    md_vol = _num(getattr(md, "volatility", None), 0.0) if md else 0.0
    md_pct5 = _num(getattr(md, "pct_chg_5d", None), 0.0) if md else 0.0
    has_market = bool(kline_ok or md_closes or md_vol > 1e-6 or abs(md_pct5) > 1e-6)
    if fin is None:
        pe_pct = 0.5 if has_market else 1.0
        pb_pct = 0.5 if has_market else 1.0
    else:
        pe_pct = _num(getattr(fin, "pe_percentile", None), 0.5)
        pb_pct = _num(getattr(fin, "pb_percentile", None), 0.5)
        # 财务对象存在但 pe/pb/roe 全为 0 且分位是默认值(0.5) -> 无数据 -> 中性
        no_values = not (_num(getattr(fin, "pe", None), 0.0) or _num(getattr(fin, "pb", None), 0.0)
                         or _num(getattr(fin, "roe", None), 0.0))
        pe_default = abs(pe_pct - 0.5) < 1e-9
        if no_values and pe_default:
            pe_pct = 0.5 if has_market else 1.0

    # 无行情且无财务 -> 直接高风险(空数据 ≠ 安全)
    if not has_market:
        return {
            "risk_level": "高",
            "volatility": round(volatility, 4),
            "max_drawdown": round(drawdown, 4),
            "valuation_risk": "高",
            "detail": "行情与财务数据均缺失, 按高风险处理",
        }

    # 1. 估值风险
    if pe_pct < 0.4:
        valuation_risk = "低"
    elif pe_pct < 0.7:
        valuation_risk = "中"
    else:
        valuation_risk = "高"

    # 2. 风险等级
    if volatility < RISK_LOW_VOL and drawdown < RISK_LOW_DRAWDOWN and pe_pct < RISK_LOW_PE_PCT:
        risk_level = "低"
    elif volatility < RISK_MID_VOL and drawdown < RISK_MID_DRAWDOWN:
        risk_level = "中"
    else:
        risk_level = "高"

    detail = (
        f"波动率{volatility:.1%}, 近20日最大回撤{drawdown:.1%}, "
        f"PE历史分位{pe_pct:.0%}, PB历史分位{pb_pct:.0%}"
    )

    return {
        "risk_level": risk_level,
        "volatility": round(volatility, 4),
        "max_drawdown": round(drawdown, 4),
        "valuation_risk": valuation_risk,
        "detail": detail,
    }


def analyze_risk_batch(stocks: list) -> list:
    """批量风险分析。
    对一组股票逐个执行 analyze_risk, 单只失败不影响其余。
    返回: [{"stock": StockProfile, "risk": {...}}, ...]
    """
    results = []
    for stock in stocks:
        try:
            risk = analyze_risk(stock)
        except Exception as e:  # noqa: BLE001 - 单只失败降级为默认风险
            logger.warning("风险分析失败 %s: %s", getattr(stock, "code", "?"), str(e)[:100])
            risk = {
                "risk_level": "高",  # 未知 -> 最保守
                "volatility": 1.0,
                "max_drawdown": 1.0,
                "valuation_risk": "高",
                "detail": "数据缺失, 按高风险处理",
            }
        results.append({"stock": stock, "risk": risk})
    return results
