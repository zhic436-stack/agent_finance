# -*- coding: utf-8 -*-
"""backtest_engine 单元测试 (mock 价格数据, 验证费用/买入持有/基准)。"""
import numpy as np
import pandas as pd
import pytest


def _fake_price_matrix(codes, start="20250101", end="20250131", seed=42):
    """合成 3 只股票的价格: A 稳定上涨, B 震荡, C 下跌。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2025-01-02", periods=60)
    idx = pd.DatetimeIndex([d.to_pydatetime().date() for d in dates])
    data = {}
    drift = {"A": 0.003, "B": 0.0, "C": -0.002}
    for c in codes:
        rets = rng.normal(drift[c], 0.01, len(dates))
        data[c] = 100 * np.cumprod(1 + rets)
    df = pd.DataFrame(data, index=idx)
    return df


def test_backtest_success_with_fees(monkeypatch):
    from src import backtest_engine as be

    codes = ["A", "B", "C"]
    monkeypatch.setattr(be, "_fetch_price_matrix", lambda *a, **k: _fake_price_matrix(codes))
    monkeypatch.setattr(be, "_get_benchmark_return", lambda *a, **k: 0.10)

    r = be.run_backtest(codes, start_date="20250101", end_date="20250131")
    assert r["error"] is None
    assert r["total_days"] > 30
    assert r["benchmark_return"] == 0.10, "基准应透传 mock 值"
    assert "total_return" in r and "sharpe" in r and "max_drawdown" in r


def test_backtest_costs_reduce_return(monkeypatch):
    """费用应使净收益低于无费用收益。"""
    from src import backtest_engine as be

    codes = ["A"]
    monkeypatch.setattr(be, "_fetch_price_matrix", lambda *a, **k: _fake_price_matrix(codes))
    monkeypatch.setattr(be, "_get_benchmark_return", lambda *a, **k: 0.0)

    r = be.run_backtest(codes, start_date="20250101", end_date="20250131")
    assert r["error"] is None
    total = r["total_return"]

    # 手动计算无费用收益对比 (买入持有单股 = 期末/期初-1)
    df = _fake_price_matrix(codes)
    gross = float(df["A"].iloc[-1] / df["A"].iloc[0] - 1)
    assert total < gross, "含费用收益应低于毛收益"
    assert abs(total - gross) < 0.02, "费用占比应合理 (~0.33%)"


def test_backtest_empty_data(monkeypatch):
    from src import backtest_engine as be

    monkeypatch.setattr(be, "_fetch_price_matrix", lambda *a, **k: None)
    r = be.run_backtest(["A"], start_date="20250101", end_date="20250131")
    assert r["total_days"] == 0
    assert r["error"] is not None


def test_backtest_equal_weight_default(monkeypatch):
    from src import backtest_engine as be

    codes = ["A", "B", "C"]
    monkeypatch.setattr(be, "_fetch_price_matrix", lambda *a, **k: _fake_price_matrix(codes))
    monkeypatch.setattr(be, "_get_benchmark_return", lambda *a, **k: 0.0)

    r = be.run_backtest(codes, start_date="20250101", end_date="20250131")
    assert r["used_codes"] == codes
    assert len(r["daily_returns"]) == r["total_days"]
