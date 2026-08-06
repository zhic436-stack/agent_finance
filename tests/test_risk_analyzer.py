"""风险分析器单元测试。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collector import FinancialData, StockProfile
from src.risk_analyzer import analyze_risk


def _kline(closes):
    return pd.DataFrame({"收盘": closes})


def test_low_risk():
    stock = StockProfile(code="1", name="low", financials=FinancialData(pe_percentile=0.2, pb_percentile=0.2))
    with patch("src.risk_analyzer.ak.stock_zh_a_hist", return_value=_kline([100, 100.2, 100.1, 100.3, 100.4, 100.5])):
        result = analyze_risk(stock)
    assert result["risk_level"] == "低"
    assert result["valuation_risk"] == "低"


def test_high_risk_from_real_kline():
    stock = StockProfile(code="3", name="high", financials=FinancialData(pe_percentile=0.9, pb_percentile=0.9))
    with patch("src.risk_analyzer.ak.stock_zh_a_hist", return_value=_kline([100, 130, 80, 125, 70, 115])):
        result = analyze_risk(stock)
    assert result["risk_level"] == "高"
    assert result["max_drawdown"] > 0


def test_fetch_failure_is_unavailable_not_zero():
    stock = StockProfile(code="4", name="empty")
    with patch("src.risk_analyzer.ak.stock_zh_a_hist", side_effect=RuntimeError("offline")):
        result = analyze_risk(stock)
    assert result["risk_level"] == "数据暂缺"
    assert result["volatility"] is None
    assert result["max_drawdown"] is None


def test_output_schema():
    stock = StockProfile(code="5", name="x", financials=FinancialData(pe_percentile=0.3))
    with patch("src.risk_analyzer.ak.stock_zh_a_hist", return_value=_kline([100, 101, 100, 102, 101, 103])):
        result = analyze_risk(stock)
    for key in ("risk_level", "volatility", "max_drawdown", "valuation_risk", "detail"):
        assert key in result, f"缺少字段 {key}"