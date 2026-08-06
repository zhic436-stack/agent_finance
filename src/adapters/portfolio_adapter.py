"""PyPortfolioOpt 适配器 (补漏块5.4): 组合优化与风险平价。

接入 PyPortfolioOpt 的 HRP (Hierarchical Risk Parity) 和 CLA/MaxSharpe。
权重约束: 和=1.0, 无负权重 (long-only)。

验证: python -c "from src.adapters.portfolio_adapter import optimize_portfolio; w=optimize_portfolio(...)"
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def optimize_portfolio(
    codes: List[str],
    expected_returns: Optional[List[float]] = None,
    cov_matrix: Optional[Any] = None,
    method: str = "hrp",
) -> Dict[str, Any]:
    """组合优化。返回 {weights: {code: w}, method, ok}。

    - method="hrp": 层次风险平价 (无需收益预测, 稳健)
    - method="max_sharpe": 最大夏普 (需 expected_returns)
    权重约束: 和=1.0, long-only (无负权重)。
    """
    import numpy as np
    from src.real_covariance import compute_covariance_matrix, compute_expected_returns

    if not codes:
        return {"weights": {}, "method": method, "ok": False, "error": "空股票列表"}

    n = len(codes)
    try:
        if cov_matrix is None:
            return {"weights": {}, "method": method, "ok": False, "error": "真实协方差数据暂缺"}
        cov = np.asarray(cov_matrix, dtype=float)
        if cov.shape != (n, n) or not np.isfinite(cov).all():
            return {"weights": {}, "method": method, "ok": False, "error": "协方差矩阵无效"}
        if method == "hrp":
            import pandas as pd
            from pypfopt import HRPOpt

            # scipy 兼容: 新版 scipy 删除 _LINKAGE_METHODS, PyPortfolioOpt 1.6 依赖它
            # 运行时注入兼容属性, 使 HRP 在新版 scipy 下可用
            try:
                import scipy.cluster.hierarchy as sch
                if not hasattr(sch, "_LINKAGE_METHODS"):
                    sch._LINKAGE_METHODS = ["single", "complete", "average",
                                            "weighted", "centroid", "median",
                                            "ward"]
            except ImportError:
                pass

            # HRPOpt 需要 DataFrame (带 .columns), 用代码作为索引
            cov_df = pd.DataFrame(cov, index=codes, columns=codes)
            hrp = HRPOpt(cov_matrix=cov_df)
            w = hrp.optimize()
        elif method == "max_sharpe":
            from pypfopt import EfficientFrontier

            if expected_returns is None:
                return {"weights": {}, "method": method, "ok": False, "error": "真实预期收益数据暂缺"}
            mu = np.asarray(expected_returns, dtype=float)
            ef = EfficientFrontier(mu, cov)
            ef.max_sharpe()
            w = ef.clean_weights()
        elif method == "min_volatility":
            from pypfopt import EfficientFrontier

            # min_volatility 只需协方差, 不需要预期收益 (mu 可为 None)
            mu = np.asarray(expected_returns, dtype=float) if expected_returns is not None else None
            ef = EfficientFrontier(mu, cov)
            ef.min_volatility()
            w = ef.clean_weights()
        else:
            return {"weights": {}, "method": method, "ok": False, "error": f"未知方法 {method}"}

        # 归一化 + 去负权重 (long-only)
        total = sum(max(0.0, float(v)) for v in w.values())
        weights = {c: round(max(0.0, float(v)) / total, 4) if total > 0 else 0.0
                   for c, v in zip(codes, w.values())}

        return {
            "weights": weights,
            "method": method,
            "ok": True,
            "sum_weights": round(sum(weights.values()), 4),
        }
    except Exception as error:  # noqa: BLE001
        logger.warning("组合优化失败: %s", str(error)[:80])
        return {
            "weights": {},
            "method": method,
            "ok": False,
            "error": str(error)[:120],
        }

if __name__ == "__main__":
    codes = ["000099", "002085", "600519", "688787"]
    r = optimize_portfolio(codes, method="hrp")
    print("OK")
    print(f"权重: {r['weights']}")
    print(f"和: {r['sum_weights']} | 无负权重: {all(v >= 0 for v in r['weights'].values())}")
