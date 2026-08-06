# -*- coding: utf-8 -*-
"""ascend_accel 昇腾加速模块测试 (numpy 降级路径, 离线确定性)。"""
import numpy as np
import pytest


def test_backend_info_structure():
    from src.ascend_accel import backend_info
    info = backend_info()
    assert "framework" in info and "device" in info and "ascend_npu" in info
    # 本机无昇腾时应为 numpy 降级; 若装了 MindSpore 则 device 为 CPU/Ascend
    assert info["device"] in ("Ascend", "CPU", "numpy")


def test_covariance_matches_numpy():
    from src.ascend_accel import covariance_matrix
    rng = np.random.default_rng(42)
    X = rng.normal(0.001, 0.02, (60, 3))
    cov = covariance_matrix(X)
    expected = np.cov(X, rowvar=False)
    np.testing.assert_allclose(cov, expected, rtol=1e-5, atol=1e-8)


def test_covariance_single_column():
    from src.ascend_accel import covariance_matrix
    rng = np.random.default_rng(1)
    X = rng.normal(0, 0.02, 40)
    cov = covariance_matrix(X)  # 1-d 输入
    assert cov.shape == (1, 1)
    assert cov[0, 0] > 0
    # 与 numpy 一致
    expected = float(np.var(X, ddof=1))
    assert abs(cov[0, 0] - expected) < 1e-10


def test_normalize01():
    from src.ascend_accel import normalize01
    out = normalize01(np.array([0.0, 5.0, 10.0]), 0.0, 10.0)
    np.testing.assert_allclose(out, [0.0, 0.5, 1.0])
    # 越界裁剪
    out2 = normalize01(np.array([-5.0, 15.0]), 0.0, 10.0)
    np.testing.assert_allclose(out2, [0.0, 1.0])
    # 零跨度安全
    out3 = normalize01(np.array([3.0, 3.0]), 3.0, 3.0)
    np.testing.assert_allclose(out3, [0.0, 0.0])


def test_covariance_insufficient_days():
    from src.ascend_accel import covariance_matrix
    cov = covariance_matrix(np.array([[1.0], [2.0]]))  # 2 行 1 列
    assert cov.shape == (1, 1)
