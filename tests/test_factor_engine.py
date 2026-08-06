"""因子引擎单元测试 (纯规则, 不依赖外部接口)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collector import FinancialData, MarketData, News, StockProfile
from src.factor_engine import (
    calc_composite_score,
    calc_event_factor,
    calc_growth_factor,
    calc_market_factor,
    calc_value_factor,
)


def make_stock() -> StockProfile:
    return StockProfile(
        code="000099",
        name="中信海直",
        concepts=["低空经济", "无人机", "通航"],
        news=[
            News(title="低空经济政策利好, eVTOL整机放量", content="..."),
            News(title="公司获批通航运营资质", content="..."),
        ],
        financials=FinancialData(
            pe=15, pb=1.5, roe=18,
            pe_percentile=0.2, pb_percentile=0.3,
            revenue_growth=0.3, profit_growth=0.4,
        ),
        market=MarketData(pct_chg_5d=0.08, volume_trend=0.8, volatility=0.03),
    )


EVENT = {
    "topic": "低空经济",
    "event_type": "政策",
    "benefited_industries": ["低空经济"],
    "keywords": ["低空经济", "eVTOL", "通航"],
}


def test_value_factor():
    v = calc_value_factor(make_stock())
    assert 0 <= v <= 100
    assert v > 50, "低PE分位+高ROE应得分偏高"


def test_growth_factor():
    g = calc_growth_factor(make_stock())
    assert 0 <= g <= 100
    assert g > 50, "高增长应得分偏高"


def test_market_factor():
    m = calc_market_factor(make_stock())
    assert 0 <= m <= 100


def test_event_factor():
    e = calc_event_factor(make_stock(), EVENT)
    assert 0 <= e <= 100
    assert e > 50, "概念+新闻全命中应高分"


def test_empty_stock_zero():
    """空股票(无任何财务/市场数据)所有因子应为 0。"""
    empty = StockProfile(code="0", name="empty")
    assert calc_value_factor(empty) == 0
    assert calc_growth_factor(empty) == 0
    assert calc_market_factor(empty) == 0
    assert calc_event_factor(empty, EVENT) == 0


def test_zero_financials_zero():
    """FinancialData 全 0 (pe/pb/roe 无值) 视为无数据, 价值/成长因子应为 0。"""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.data_collector import FinancialData
    stock = StockProfile(
        code="1", name="zero",
        financials=FinancialData(),  # 全默认 0
    )
    assert calc_value_factor(stock) == 0
    assert calc_growth_factor(stock) == 0


def test_composite():
    factors = {"event": 80, "value": 70, "growth": 75, "market": 60}
    c = calc_composite_score(factors)
    assert 0 <= c <= 100
    assert c == calc_composite_score({"event": 80, "value": 70, "growth": 75, "market": 60})


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
