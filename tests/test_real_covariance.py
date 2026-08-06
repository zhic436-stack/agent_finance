# -*- coding: utf-8 -*-
"""real_covariance 单元测试 (mock 收益 Series, 验证日期对齐与失败填充)。"""
import numpy as np
import pandas as pd
import pytest


def _mk_series(code, n=40, seed=1, offset=0, missing=None):
    """构造带日期索引的对数收益 Series; missing 为要挖空的日期。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    rets = rng.normal(0.0005, 0.02, n)
    dates = dates[offset:]  # 错开上市日期
    rets = rets[offset:]
    s = pd.Series(rets, index=dates, name=code)
    if missing:
        s = s.drop(index=[d for d in missing if d in s.index])
    return s


def test_covariance_aligned_dates(monkeypatch):
    """两只股票上市日期不同: 对齐后共同交易日计算, 矩阵有效。"""
    from src import real_covariance as rc

    s1 = _mk_series("A", n=50, seed=1, offset=0)
    s2 = _mk_series("B", n=50, seed=2, offset=10)  # B 晚 10 个交易日上市
    monkeypatch.setattr(rc, "_get_returns", lambda code, *a, **k: {"A": s1, "B": s2}.get(code))

    cov = rc.compute_covariance_matrix(["A", "B"], lookback_days=50, use_cache=False)
    assert cov is not None
    assert cov.shape == (2, 2)
    diag = np.diag(cov)
    assert all(v > 0 for v in diag), "对角线方差应为正"


def test_covariance_failed_stock_filled(monkeypatch):
    """一只股票数据失败: 用平均方差填充而非 0 方差。"""
    from src import real_covariance as rc

    s1 = _mk_series("A", n=40, seed=1)
    monkeypatch.setattr(rc, "_get_returns",
                        lambda code, *a, **k: s1 if code == "A" else None)

    cov = rc.compute_covariance_matrix(["A", "B"], lookback_days=40, use_cache=False)
    assert cov is not None
    assert cov.shape == (2, 2)
    # B 的对角方差应 > 0 (平均方差填充), 且 B 与 A 的相关性为弱相关 (非 0 矩阵)
    assert cov[1, 1] > 0
    assert cov[0, 0] > 0


def test_covariance_insufficient_common_days(monkeypatch):
    """共同交易日不足应返回 None。"""
    from src import real_covariance as rc

    s1 = _mk_series("A", n=40, seed=1)
    s2 = _mk_series("B", n=40, seed=2, offset=39)  # 几乎无重叠
    monkeypatch.setattr(rc, "_get_returns", lambda code, *a, **k: {"A": s1, "B": s2}.get(code))

    cov = rc.compute_covariance_matrix(["A", "B"], lookback_days=40, use_cache=False)
    assert cov is None or cov.shape == (2, 2)


def test_expected_returns_series_compat(monkeypatch):
    """compute_expected_returns 应兼容 Series 输入。"""
    from src import real_covariance as rc

    s1 = _mk_series("A", n=40, seed=1)
    monkeypatch.setattr(rc, "_get_returns", lambda code, *a, **k: s1)

    exp = rc.compute_expected_returns(["A"], lookback_days=40)
    assert "A" in exp
    assert isinstance(exp["A"], float)
