# -*- coding: utf-8 -*-
"""Real covariance matrix from historical price data.
Replaces diagonal (fake) covariance with actual pairwise correlations.
"""
from __future__ import annotations
import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Cache for historical returns (Series: index=日期, value=对数收益)
_RETURNS_CACHE: Dict[str, Tuple[float, "pd.Series"]] = {}
_CACHE_TTL = 3600  # 1 hour


def compute_covariance_matrix(
    codes: List[str],
    lookback_days: int = 60,
    use_cache: bool = True,
) -> Optional[np.ndarray]:
    """Compute real covariance matrix from historical price data.

    Args:
        codes: List of stock codes (e.g., ["000001", "600000"])
        lookback_days: Number of trading days to use
        use_cache: Whether to use cached returns

    Returns:
        n x n covariance matrix, or None if computation fails.
    """
    n = len(codes)
    if n < 2:
        # Single stock: return scalar variance
        returns = _get_returns(codes[0], lookback_days, use_cache)
        if returns is not None:
            var = float(np.var(returns.values, ddof=1))
            return np.array([[var]])
        return None

    # Fetch returns for all stocks
    all_returns: Dict[str, "pd.Series"] = {}
    failed = []
    for code in codes:
        ret = _get_returns(code, lookback_days, use_cache)
        if ret is not None:
            all_returns[code] = ret
        else:
            failed.append(code)

    if not all_returns:
        logger.warning("No return data for any stock")
        return None

    if failed:
        logger.info("Skipped %d stocks with no data: %s", len(failed), failed)

    # 按日期对齐 (pd.concat + dropna), 避免停牌/上市时间不同导致的收益向量错位
    import pandas as pd
    ret_df = pd.concat(all_returns, axis=1).dropna()
    if len(ret_df) < 5:
        logger.warning("Insufficient common trading days: %d", len(ret_df))
        return None

    valid_codes = list(ret_df.columns)
    # 强制 2-d (单列时 to_numpy 可能返回 1-d, 导致 np.cov 返回标量)
    returns_matrix = np.column_stack([ret_df[c].to_numpy() for c in ret_df.columns])

    # Compute covariance: 昇腾 MindSpore 加速优先, numpy 兜底 (np.cov 单变量 0-d 已内部处理)
    from src.ascend_accel import covariance_matrix as _ascend_cov
    cov = np.atleast_2d(_ascend_cov(returns_matrix))

    if failed:
        # 失败股票填充平均方差 (而非 0 方差, 避免优化器视为零风险病态集中)
        var_diag = float(np.mean(np.var(returns_matrix, axis=0, ddof=1))) if returns_matrix.size else 0.01
        full_cov = np.full((n, n), var_diag * 0.5)  # 与其他资产弱相关
        for i in range(n):
            full_cov[i, i] = var_diag
        for i, ci in enumerate(valid_codes):
            orig_i = codes.index(ci)
            for j, cj in enumerate(valid_codes):
                orig_j = codes.index(cj)
                full_cov[orig_i, orig_j] = cov[i, j]
        cov = full_cov

    return cov


def _get_returns(
    code: str,
    lookback_days: int = 60,
    use_cache: bool = True,
) -> Optional["pd.Series"]:
    """Get daily log returns for a stock (index=交易日, 供按日期对齐)."""
    import pandas as pd

    cache_key = f"{code}_{int(time.time() // _CACHE_TTL)}"
    if use_cache and cache_key in _RETURNS_CACHE:
        _, rets = _RETURNS_CACHE[cache_key]
        return rets[-lookback_days:] if len(rets) > lookback_days else rets

    try:
        import akshare as ak
        from datetime import datetime, timedelta

        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=lookback_days * 2)).strftime("%Y%m%d")

        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start, end_date=end, adjust="qfq",
        )
        if df is None or len(df) < 10:
            return None

        closes = df["收盘"].astype(float).values
        returns = np.diff(np.log(closes))
        dates = pd.to_datetime(df["日期"].iloc[1:]).reset_index(drop=True)
        series = pd.Series(returns, index=dates, name=code)

        _RETURNS_CACHE[cache_key] = (time.time(), series)
        return series[-lookback_days:] if len(series) > lookback_days else series

    except ImportError:
        return None
    except Exception as error:
        logger.debug("Returns fetch failed for %s: %s", code, str(error)[:80])
        return None


def compute_expected_returns(
    codes: List[str],
    lookback_days: int = 60,
) -> Dict[str, float]:
    """Compute annualized expected returns from historical data."""
    expected = {}
    for code in codes:
        rets = _get_returns(code, lookback_days)
        if rets is not None and len(rets) > 0:
            annual_ret = float(rets.mean()) * 252
        else:
            continue
        expected[code] = annual_ret
    return expected
