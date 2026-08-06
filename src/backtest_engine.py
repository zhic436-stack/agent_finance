# -*- coding: utf-8 -*-
"""Minimal real backtest engine.
Replaces the placeholder backtest_engine with working implementation.
Computes: cumulative returns, Sharpe ratio, max drawdown, annualized metrics.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout
import time

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS = 252


def run_backtest(
    codes: List[str],
    weights: Optional[Dict[str, float]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lookback_days: int = 252,
    initial_capital: float = 1_000_000,
    benchmark_code: str = "000300",
) -> Dict[str, Any]:
    """Run a realistic portfolio backtest.

    Args:
        codes: Stock codes to include
        weights: Portfolio weights (equal-weight if None)
        start_date: Start date YYYYMMDD (default: 1 year ago)
        end_date: End date YYYYMMDD (default: today)
        lookback_days: Days to look back if dates not specified
        initial_capital: Starting capital
        benchmark_code: Benchmark index code

    Returns:
        Dict with cumulative_return, sharpe_ratio, max_drawdown,
        annual_return, annual_volatility, benchmark_return, etc.
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=lookback_days * 2)).strftime("%Y%m%d")

    # Default to equal weight
    if weights is None:
        w = 1.0 / len(codes) if codes else 0.0
        weights = {c: w for c in codes}

    # Fetch price data
    price_data = _fetch_price_matrix(codes, start_date, end_date)
    if price_data is None or price_data.shape[1] < 1:
        return _empty_backtest_result()

    # Compute portfolio returns
    returns = price_data.pct_change().dropna()
    if returns.empty:
        return _empty_backtest_result()

    # Weighted portfolio returns
    valid_codes = [c for c in codes if c in returns.columns]
    if not valid_codes:
        return _empty_backtest_result()

    port_weights = np.array([weights.get(c, 0.0) for c in valid_codes])
    port_weights = port_weights / port_weights.sum()  # Normalize

    # 组合净值路径: 买入持有 (期初按权重买入, 之后持仓自然漂移, 而非每日再平衡)
    cum_path = (1 + returns[valid_codes]).cumprod()
    nav = (cum_path * port_weights).sum(axis=1)
    port_returns = nav.pct_change().dropna()
    if port_returns.empty:
        return _empty_backtest_result()

    # 交易成本 (BACKTEST_CONFIG): 期初买入佣金+滑点, 期末卖出佣金+印花税+滑点
    try:
        from config import BACKTEST_CONFIG
        cfg = BACKTEST_CONFIG
    except Exception:  # noqa: BLE001
        cfg = {}
    buy_cost = float(cfg.get("commission_rate_buy", 0.00015)) + float(cfg.get("slippage", 0.001))
    sell_cost = float(cfg.get("commission_rate_sell", 0.00015)) + float(cfg.get("stamp_tax_rate", 0.001)) + float(cfg.get("slippage", 0.001))
    nav_final = float(nav.iloc[-1]) * (1 - buy_cost) * (1 - sell_cost)
    cum_return = nav_final - 1.0
    total_return = cum_return

    # Sharpe ratio (无风险利率取 config.cash_interest_rate)
    rf_annual = float(cfg.get("cash_interest_rate", 0.015)) if cfg else 0.015
    excess = port_returns - rf_annual / TRADING_DAYS
    sharpe = float(np.sqrt(TRADING_DAYS) * excess.mean() / (excess.std() + 1e-10))

    # Max drawdown (基于含权重的组合净值路径)
    cum = nav
    peak = cum.expanding().max()
    drawdown = (cum - peak) / peak
    max_dd = float(abs(drawdown.min()))

    # Annualized
    annual_ret = float((1 + total_return) ** (TRADING_DAYS / len(port_returns)) - 1) if total_return > -1 else -1.0
    annual_vol = float(port_returns.std() * np.sqrt(TRADING_DAYS))

    # Benchmark
    bench_ret = _get_benchmark_return(benchmark_code, start_date, end_date)

    # Win rate
    positive_days = int((port_returns > 0).sum())
    total_days = len(port_returns)
    win_rate = float(positive_days / total_days) if total_days > 0 else 0.0

    return {
        "cumulative_return": round(cum_return, 6),
        "total_return": round(cum_return, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 6),
        "annual_return": round(annual_ret, 6),
        "annual_volatility": round(annual_vol, 6),
        "volatility": round(annual_vol, 6),
        "benchmark_return": round(bench_ret, 6),
        "win_rate": round(win_rate, 6),
        "daily_returns": [float(value) for value in port_returns],
        "return_dates": [str(value.date()) for value in port_returns.index],
        "total_days": total_days,
        "positive_days": positive_days,
        "start_date": start_date,
        "end_date": end_date,
        "used_codes": valid_codes,
        "requested_codes": codes,
        "error": None,
    }


def _market_symbol(code: str) -> str:
    if code.startswith(("4", "8", "9")):
        return f"bj{code}"
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _fetch_single_stock(code, start_date, end_date):
    """优先东财，失败时切换新浪真实日线接口。"""
    import akshare as ak

    try:
        frame = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if frame is not None and not frame.empty and "收盘" in frame.columns:
            return code, frame
    except Exception as error:
        logger.info("东财行情失败 %s: %s", code, str(error)[:80])

    frame = ak.stock_zh_a_daily(
        symbol=_market_symbol(code),
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
    )
    if frame is None or frame.empty or "close" not in frame.columns:
        return code, None
    normalized = pd.DataFrame({
        "日期": pd.to_datetime(frame["date"]),
        "收盘": frame["close"].astype(float),
    })
    return code, normalized

def _fetch_price_matrix(codes, start_date, end_date, timeout_per_stock=4):
    """并发拉取真实行情；允许部分股票成功，不使用随机行情兜底。"""
    try:
        import akshare  # noqa: F401
    except ImportError:
        logger.warning("未安装 akshare，无法拉取回测行情")
        return None

    all_prices = {}
    worker_count = min(4, len(codes))
    executor = ThreadPoolExecutor(max_workers=worker_count)
    futures = {
        executor.submit(_fetch_single_stock, code, start_date, end_date): code
        for code in codes
    }
    try:
        for future in as_completed(futures, timeout=max(8, timeout_per_stock * worker_count)):
            code = futures[future]
            try:
                _, frame = future.result(timeout=timeout_per_stock)
                if frame is None or frame.empty or "收盘" not in frame.columns:
                    continue
                date_values = frame["日期"] if "日期" in frame.columns else frame.index
                series = pd.Series(
                    frame["收盘"].astype(float).to_numpy(),
                    index=pd.to_datetime(date_values),
                    name=code,
                )
                if len(series) >= 20:
                    all_prices[code] = series
            except Exception as error:
                logger.info("回测行情拉取失败 %s: %s", code, str(error)[:80])
    except FutureTimeout:
        logger.warning("回测行情拉取超时，使用已成功返回的股票")
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    if not all_prices:
        return None
    prices = pd.DataFrame(all_prices).sort_index().ffill().dropna()
    return prices if len(prices) >= 20 else None

def _get_benchmark_return(code: str, start: str, end: str) -> float:
    """Get benchmark return over period."""
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol=f"sh{code}")
        if df is not None and len(df) > 0:
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                start_dt = pd.to_datetime(start)
                end_dt = pd.to_datetime(end)
                mask = (df["date"] >= start_dt) & (df["date"] <= end_dt)
                period = df[mask]
                if len(period) > 1:
                    close_col = "close" if "close" in period.columns else "收盘"
                    return float(period[close_col].iloc[-1] / period[close_col].iloc[0] - 1)
    except Exception:
        pass
    return 0.0


def _empty_backtest_result() -> Dict[str, Any]:
    return {
        "cumulative_return": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
        "annual_return": 0.0,
        "annual_volatility": 0.0,
        "benchmark_return": 0.0,
        "win_rate": 0.0,
        "total_days": 0,
        "positive_days": 0,
        "error": "真实历史行情不足，暂时无法完成回测。请稍后重试或更换股票池。",
    }
