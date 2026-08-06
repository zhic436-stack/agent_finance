"""组合优化适配器测试: HRP/最大夏普/最小波动三策略。"""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.adapters.portfolio_adapter import optimize_portfolio

CODES = ["A", "B", "C"]
COV = np.diag([0.04, 0.06, 0.03])
RETS = [0.08, 0.12, 0.06]

def test_hrp_weights():
    r = optimize_portfolio(CODES, cov_matrix=COV, method="hrp")
    assert r["ok"], f"HRP失败: {r.get('error')}"
    assert abs(r["sum_weights"] - 1.0) < 0.01
    assert all(v >= 0 for v in r["weights"].values())

def test_max_sharpe_weights():
    r = optimize_portfolio(CODES, expected_returns=RETS, cov_matrix=COV, method="max_sharpe")
    assert r["ok"]
    assert abs(r["sum_weights"] - 1.0) < 0.01

def test_min_volatility_weights():
    r = optimize_portfolio(CODES, expected_returns=RETS, cov_matrix=COV, method="min_volatility")
    assert r["ok"]
    assert abs(r["sum_weights"] - 1.0) < 0.01

def test_empty_codes():
    r = optimize_portfolio([], method="hrp")
    assert r["ok"] is False

def test_unknown_method():
    r = optimize_portfolio(CODES, method="unknown")
    assert r["ok"] is False

def test_invalid_covariance_fails_closed():
    r = optimize_portfolio(CODES, cov_matrix="bad", method="hrp")
    assert r["ok"] is False
    assert r["weights"] == {}

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
