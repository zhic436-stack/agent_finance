"""回测数据适配器: 将因子分析结果转换为回测引擎所需格式。

对接 Codex 开发的 backtest_engine:
- adapt_to_backtest(stock_results) -> DataFrame (因子/信号/候选池)
- 依赖检查: backtest_engine 模块可用时自动启用, 否则安全降级

设计: 本适配器只做格式转换, 不包含任何回测逻辑 (回测由 backtest_engine 负责)。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def backtest_available() -> bool:
    """Check if real backtest engine is available."""
    try:
        from src.backtest_engine import run_backtest
        return True
    except ImportError:
        return False


def run_portfolio_backtest(
    stock_results: list,
    strategy: str = "equal_weight",
) -> dict:
    """使用真实历史行情执行组合回测。"""
    from src.backtest_engine import run_backtest

    valid_items = [item for item in stock_results if item.get("stock") and getattr(item["stock"], "code", "")]
    codes = list(dict.fromkeys(str(item["stock"].code) for item in valid_items))[:8]
    if not codes:
        return {"error": "没有可用于回测的股票代码。"}

    if strategy in ("multi_factor", "composite"):
        factor_key = "composite"
    elif strategy in ("value", "growth", "momentum", "quality"):
        factor_key = {
            "value": "value",
            "growth": "growth",
            "momentum": "market",
            "quality": "value",
        }[strategy]
    else:
        factor_key = None

    if factor_key:
        raw_scores = {
            str(item["stock"].code): max(0.0, float(item.get("factors", {}).get(factor_key, 0) or 0))
            for item in valid_items
            if str(item["stock"].code) in codes
        }
        score_total = sum(raw_scores.values())
        weights = (
            {code: raw_scores.get(code, 0.0) / score_total for code in codes}
            if score_total > 0
            else {code: 1.0 / len(codes) for code in codes}
        )
    else:
        weights = {code: 1.0 / len(codes) for code in codes}

    return run_backtest(codes, weights=weights)

def adapt_to_backtest(stock_results: List[Dict[str, Any]]) -> "Optional[Any]":
    """将因子分析结果转换为回测引擎所需的格式。

    输入: pipeline.run_analysis 的 stock_results
          [{"stock": StockProfile, "factors": {...}, "risk": {...}}, ...]

    输出 (回测引擎可用时): pandas.DataFrame, 列:
        code, name, composite, event, value, growth, market, risk_level
    回测引擎不可用: 返回 None (UI 可提示"回测引擎尚未接入")。

    如果回测引擎需要更多字段 (如历史收益率序列), 在 backtest_engine
    交付后在此补充。
    """
    if not backtest_available():
        logger.info("回测引擎未接入, adapt_to_backtest 返回 None")
        return None

    try:
        import pandas as pd

        rows = []
        for r in stock_results:
            stock = r.get("stock")
            factors = r.get("factors", {})
            risk = r.get("risk", {})
            rows.append({
                "code": getattr(stock, "code", ""),
                "name": getattr(stock, "name", ""),
                "composite": factors.get("composite", 0),
                "event": factors.get("event", 0),
                "value": factors.get("value", 0),
                "growth": factors.get("growth", 0),
                "market": factors.get("market", 0),
                "risk_level": risk.get("risk_level", "未知"),
            })
        return pd.DataFrame(rows)
    except Exception as e:  # noqa: BLE001
        logger.warning("适配回测数据失败: %s", str(e)[:100])
        return None


def get_backtest_signal(prices_df: "Any", factor_df: "Any", strategy: str = "multi_factor") -> "Any":
    """生成回测信号 (包装: 若 backtest_engine 提供信号生成则转发)。

    回测引擎未交付前, 返回 None。Codex 交付后按 engine API 对接。
    """
    if not backtest_available():
        return None
    try:
        from src.strategy_library import load_strategy
        from src.backtest_engine import generate_signals

        strat = load_strategy(strategy)
        return generate_signals(factor_df, prices_df, strat)
    except (ImportError, AttributeError) as e:
        logger.warning("回测信号生成未就绪: %s", str(e)[:100])
        return None
