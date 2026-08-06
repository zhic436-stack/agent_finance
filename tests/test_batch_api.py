"""批量接口测试: compute_all_factors_batch / analyze_risk_batch。

验证 UI 依赖的批量接口正确性。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collector import FinancialData, MarketData, StockInfo, StockProfile
from src.factor_engine import compute_all_factors_batch
from src.risk_analyzer import analyze_risk_batch

EVENT = {"topic": "低空经济", "benefited_industries": ["低空经济"], "keywords": ["低空经济"]}


def make_stock(code: str, name: str) -> StockProfile:
    return StockProfile(
        code=code,
        name=name,
        concepts=["低空经济"],
        financials=FinancialData(pe=10, pb=1, roe=15, pe_percentile=0.3, pb_percentile=0.3,
                                 revenue_growth=0.2, profit_growth=0.2),
        market=MarketData(pct_chg_5d=0.05, volume_trend=0.6, volatility=0.03, drawdown=0.05,
                          closes=[10, 10.2, 10.4, 10.3, 10.5], volumes=[1, 2, 3, 4, 5]),
    )


def test_factors_batch_shape():
    stocks = [make_stock("1", "A"), make_stock("2", "B")]
    results = compute_all_factors_batch(stocks, EVENT)
    assert len(results) == 2
    for r in results:
        assert r["stock"] in stocks
        for key in ("event", "value", "growth", "market", "composite"):
            assert key in r["factors"], f"缺因子 {key}"


def test_factors_batch_one_bad():
    """单只失败不影响其余 (构造会抛异常的股票)。"""
    good = make_stock("1", "A")

    class BadStock:
        code = "bad"
        name = "bad"

        @property
        def news(self):
            raise RuntimeError("boom")

        @property
        def market(self):
            raise RuntimeError("boom")

        @property
        def financials(self):
            raise RuntimeError("boom")

        @property
        def concepts(self):
            raise RuntimeError("boom")

    results = compute_all_factors_batch([good, BadStock()], EVENT)
    assert results[0]["factors"]["composite"] > 0
    assert results[1]["factors"]["composite"] == 0  # 失败 -> 全 0


def test_risk_batch_shape():
    stocks = [make_stock("1", "A"), make_stock("2", "B")]
    results = analyze_risk_batch(stocks)
    assert len(results) == 2
    for r in results:
        assert r["risk"]["risk_level"] in ("低", "中", "高", "数据暂缺")
        assert "volatility" in r["risk"]


def test_risk_batch_mixed():
    high = StockProfile(code="h", name="high", market=MarketData(volatility=0.5, drawdown=0.4))
    low = make_stock("l", "low")
    results = analyze_risk_batch([high, low])
    by_code = {r["stock"].code: r["risk"]["risk_level"] for r in results}
    assert by_code["h"] in ("高", "中", "低", "数据暂缺")
    assert by_code["l"] in ("低", "中", "高", "数据暂缺")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
