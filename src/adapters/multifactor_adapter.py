"""Multi-factor-Model 适配器 (补漏块5.3): Alpha101 风格因子扩展。

借鉴 Parsnip77/Multi-factor-Model 的因子复现思想 (WorldQuant Alpha101 模式),
在本项目数据结构上实现可计算的因子集。由于该项目数据准备依赖特定日线格式,
本适配器用我们的 StockProfile/行情数据计算等价因子, 诚实标注"借鉴模式"。

因子: 动量/波动/量价/估值 四类, 计算后归一化到 0-100, 供 factor_engine 扩展。

验证: python -c "from src.adapters.multifactor_adapter import compute_alpha_factors; ..."
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 可计算因子清单 (基于已有行情/财务数据, 借鉴 Alpha101 模式)
ALPHA_FACTORS = ["momentum", "volatility", "volume_price", "valuation", "quality"]


def _norm01(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def compute_alpha_factors(stock: Any, event: Dict[str, Any] | None = None) -> Dict[str, float]:
    """计算 Alpha101 风格因子 (0-100)。任一因子缺失返回 0, 不抛异常。"""
    event = event or {}
    factors: Dict[str, float] = {}
    md = getattr(stock, "market", None)
    fin = getattr(stock, "financials", None)

    # 1. 动量因子 (Alpha101: 过去 N 日收益排名)
    try:
        pct5 = float(getattr(md, "pct_chg_5d", 0.0) or 0.0) if md else 0.0
        factors["momentum"] = round(_norm01(pct5, -0.10, 0.10) * 100, 2)
    except Exception:
        factors["momentum"] = 0.0

    # 2. 波动因子 (Alpha101: 收益标准差反比)
    try:
        vol = float(getattr(md, "volatility", 0.0) or 0.0) if md else 0.0
        # 低波动偏好: 波动越小分越高
        factors["volatility"] = round((1.0 - _norm01(vol, 0.0, 0.05)) * 100, 2)
    except Exception:
        factors["volatility"] = 0.0

    # 3. 量价因子 (Alpha101: 量价背离/协同)
    try:
        vol_trend = float(getattr(md, "volume_trend", 0.0) or 0.0) if md else 0.0
        pct5 = float(getattr(md, "pct_chg_5d", 0.0) or 0.0) if md else 0.0
        # 放量上涨 = 高量价协同; 缩量上涨 = 低
        synergy = (pct5 > 0 and vol_trend > 0.5) or (pct5 < 0 and vol_trend < 0.5)
        factors["volume_price"] = round((vol_trend * 50 + (50 if synergy else 0)) / 100 * 100, 2)
        factors["volume_price"] = min(100.0, factors["volume_price"])
    except Exception:
        factors["volume_price"] = 0.0

    # 4. 估值因子 (PE/PB 低估值偏好)
    try:
        pe = float(getattr(fin, "pe", 0.0) or 0.0) if fin else 0.0
        pb = float(getattr(fin, "pb", 0.0) or 0.0) if fin else 0.0
        if pe > 0 and pb > 0:
            pe_score = 1.0 - _norm01(pe, 0.0, 60.0)
            pb_score = 1.0 - _norm01(pb, 0.0, 10.0)
            factors["valuation"] = round((pe_score * 0.6 + pb_score * 0.4) * 100, 2)
        else:
            factors["valuation"] = 50.0  # 无数据中性
    except Exception:
        factors["valuation"] = 50.0

    # 5. 质量因子 (ROE 高 = 高质量)
    try:
        roe = float(getattr(fin, "roe", 0.0) or 0.0) if fin else 0.0
        factors["quality"] = round(_norm01(roe, 0.0, 0.30) * 100, 2)
    except Exception:
        factors["quality"] = 0.0

    return factors


def compute_alpha_composite(factor_scores: Dict[str, float]) -> float:
    """Alpha101 风格因子综合 (等权)。"""
    if not factor_scores:
        return 0.0
    vals = [v for v in factor_scores.values() if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


if __name__ == "__main__":
    from src.data_collector import StockProfile, FinancialData, MarketData

    s = StockProfile(
        code="000099", name="测试",
        financials=FinancialData(pe=20, pb=2, roe=0.15),
        market=MarketData(pct_chg_5d=0.05, volume_trend=0.7, volatility=0.02),
    )
    f = compute_alpha_factors(s)
    print("OK")
    print(f"Alpha因子: {f}")
    print(f"综合: {compute_alpha_composite(f)}")
