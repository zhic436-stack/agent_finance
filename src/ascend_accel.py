# -*- coding: utf-8 -*-
"""昇腾加速模块: 基于 MindSpore (昇腾原生 AI 框架) 的核心计算实现。

设计目标 (合规 + 可运行):
- 代码为真实的 MindSpore 算子实现 (ops.MatMul / ops.ReduceMean / 张量运算),
  在昇腾环境 (有 MindSpore + NPU) 下自动使用昇腾算力跑通真实代码。
- 本机无 MindSpore 时自动降级 numpy (CPU 开发/测试可用, 结果一致)。
- 提供 backend_info() 供 UI/文档展示当前昇腾技术栈状态。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np

logger = logging.getLogger(__name__)

# ============ 昇腾后端检测 ============
_HAS_MINDSPORE = False
_MS_VERSION: str | None = None
_DEVICE: str = "numpy"  # "Ascend" / "CPU" / "numpy"

try:
    import mindspore  # noqa: F401 - 昇腾原生 AI 框架
    import mindspore.ops as ops
    from mindspore import Tensor

    _HAS_MINDSPORE = True
    _MS_VERSION = getattr(mindspore, "__version__", "unknown")

    # 优先设置设备为昇腾 NPU; 无 NPU 时退回 CPU (保证可运行)
    try:
        from mindspore import context
        context.set_context(device_target="Ascend")
        _DEVICE = "Ascend"
    except Exception:  # noqa: BLE001
        try:
            from mindspore import context
            context.set_context(device_target="CPU")
            _DEVICE = "CPU"
        except Exception:  # noqa: BLE001
            _DEVICE = "unknown"
except ImportError:
    _HAS_MINDSPORE = False
    _MS_VERSION = None
    _DEVICE = "numpy"

_ops = None
if _HAS_MINDSPORE:
    _ops = ops


def backend_info() -> Dict[str, Any]:
    """返回昇腾技术栈状态 (供 UI/文档展示)。"""
    return {
        "framework": "MindSpore" if _HAS_MINDSPORE else "numpy(fallback)",
        "mindspore_version": _MS_VERSION,
        "device": _DEVICE,
        "ascend_npu": _DEVICE == "Ascend",
        "note": "昇腾原生算力已启用" if _DEVICE == "Ascend" else
                ("MindSpore 可用(CPU 模式)" if _HAS_MINDSPORE else "本机无 MindSpore, 使用 numpy 降级; 昇腾环境自动启用昇腾算力"),
    }


# ============ MindSpore 算子实现 ============

def _covariance_mindspore(returns_matrix: np.ndarray) -> np.ndarray:
    """MindSpore 实现: 协方差矩阵 (昇腾 NPU 可直接加速)。

    cov = X'X / (n-1), X 为按列中心化的收益矩阵 (float32)。
    """
    X = Tensor(returns_matrix.astype(np.float32), mindspore.float32)
    n = X.shape[0]
    mean = _ops.ReduceMean(keep_dims=True)(X, 0)
    Xc = X - mean
    cov = _ops.MatMul(transpose_a=True)(Xc, Xc)
    cov = cov / float(n - 1)
    return cov.asnumpy()


def _normalize_mindspore(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """MindSpore 实现: 线性归一化到 0~1 (因子引擎使用)。"""
    t = Tensor(np.asarray(values, dtype=np.float32), mindspore.float32)
    span = float(hi - lo) if hi != lo else 1.0
    out = (t - float(lo)) / span
    return np.clip(out.asnumpy(), 0.0, 1.0)


# ============ 公共接口 (MindSpore 优先, numpy 兜底) ============

def covariance_matrix(returns_matrix: np.ndarray) -> np.ndarray:
    """协方差矩阵计算: 昇腾 MindSpore 加速, 不可用时 numpy 兜底。结果与 np.cov(rowvar=False) 一致。"""
    arr = np.asarray(returns_matrix, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    # 单列/小矩阵走 numpy (与 np.cov 行为一致, 避免 0-d 边界)
    if arr.shape[1] < 2:
        var = float(np.var(arr, axis=0, ddof=1)) if len(arr) > 1 else 0.0
        return np.atleast_2d(np.array([var]))
    if _HAS_MINDSPORE:
        try:
            return _covariance_mindspore(arr)
        except Exception as e:  # noqa: BLE001
            logger.warning("MindSpore 协方差计算失败, 降级 numpy: %s", str(e)[:80])
    return np.atleast_2d(np.cov(arr, rowvar=False))


def normalize01(values, lo: float, hi: float) -> np.ndarray:
    """线性归一化到 0~1: 昇腾 MindSpore 加速, 不可用时 numpy 兜底。"""
    arr = np.asarray(values, dtype=np.float64)
    span = float(hi - lo) if hi != lo else 1.0
    if _HAS_MINDSPORE:
        try:
            return _normalize_mindspore(arr, lo, hi)
        except Exception as e:  # noqa: BLE001
            logger.warning("MindSpore 归一化失败, 降级 numpy: %s", str(e)[:80])
    return np.clip((arr - float(lo)) / span, 0.0, 1.0)
