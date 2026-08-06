# -*- coding: utf-8 -*-
"""策略回测页面。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.components.footer import render_footer


STRATEGY_LABELS = {
    "multi_factor": "多因子综合策略",
    "value": "价值投资策略",
    "growth": "成长投资策略",
    "quality": "质量筛选策略",
    "momentum": "动量策略",
    "equal_weight": "等权配置策略",
}


def _render_result(result):
    used_codes = result.get("used_codes") or []
    requested_codes = result.get("requested_codes") or []
    if used_codes:
        st.success(f"回测完成：成功使用 {len(used_codes)} 只股票、{result.get('total_days', 0)} 个交易日。")
        if len(used_codes) < len(requested_codes):
            st.warning(f"其中 {len(requested_codes) - len(used_codes)} 只股票因历史行情不足已自动跳过。")

    metric_columns = st.columns(3)
    metrics = [
        ("累计收益率", f"{result.get('total_return', 0):.2%}"),
        ("夏普比率", f"{result.get('sharpe', 0):.3f}"),
        ("最大回撤", f"{result.get('max_drawdown', 0):.2%}"),
        ("年化波动率", f"{result.get('volatility', 0):.2%}"),
        ("上涨天数占比", f"{result.get('win_rate', 0):.2%}"),
        ("年化收益率", f"{result.get('annual_return', 0):.2%}"),
    ]
    for index, (label, value) in enumerate(metrics):
        with metric_columns[index % 3]:
            st.metric(label, value)

    daily_returns = result.get("daily_returns") or []
    return_dates = result.get("return_dates") or []
    if daily_returns and len(daily_returns) == len(return_dates):
        returns = pd.Series(daily_returns, index=pd.to_datetime(return_dates), dtype="float64")
        net_value = (1 + returns).cumprod()
        figure = go.Figure()
        figure.add_trace(go.Scatter(
            x=net_value.index,
            y=net_value.values,
            mode="lines",
            name="组合净值",
            line={"color": "#3b82f6", "width": 2.5},
            hovertemplate="日期：%{x|%Y-%m-%d}<br>净值：%{y:.4f}<extra></extra>",
        ))
        figure.update_layout(
            title="组合净值曲线",
            height=420,
            margin={"l": 30, "r": 20, "t": 55, "b": 30},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#f8fafc", "family": "Microsoft YaHei, sans-serif"},
            xaxis_title="日期",
            yaxis_title="净值",
            hovermode="x unified",
        )
        st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def render():
    st.title("策略回测")
    if (st.session_state.get("analysis_result") or {}).get("_from_demo"):
        st.caption("说明：当前展示离线缓存的预计算结果（演示数据，非实时行情）。")

    st.caption("基于真实历史行情检验策略表现；不会使用随机数据冒充回测结果。")

    from src.backtest_adapter import backtest_available, run_portfolio_backtest

    result = st.session_state.get("analysis_result")
    if not result or not result.get("stock_results"):
        st.info("暂无股票池，请先在事件分析页面运行一次分析。")
        render_footer()
        return

    if not backtest_available():
        st.error("回测引擎未能正常加载，请检查依赖。")
        render_footer()
        return

    st.markdown("### 策略设置")
    strategy = st.selectbox(
        "选择回测策略",
        list(STRATEGY_LABELS),
        format_func=lambda value: STRATEGY_LABELS[value],
    )
    st.caption("默认回看约一年交易数据；行情不可用的股票会被跳过。")

    if st.button("运行回测", type="primary", width="stretch"):
        with st.spinner("正在拉取真实历史行情并计算回测指标..."):
            try:
                backtest_result = run_portfolio_backtest(
                    result["stock_results"],
                    strategy=strategy,
                )
            except Exception as error:
                backtest_result = {"error": f"回测执行失败：{error}"}
        st.session_state["backtest_result"] = backtest_result
        st.session_state["backtest_strategy"] = strategy

    backtest_result = st.session_state.get("backtest_result")
    if backtest_result:
        if backtest_result.get("error"):
            st.error(backtest_result["error"])
            st.info("请检查网络连接，或在事件分析页面更换包含有效历史行情的股票池后重试。")
        else:
            st.markdown(f"### 回测结果 · {STRATEGY_LABELS.get(st.session_state.get('backtest_strategy'), '')}")
            _render_result(backtest_result)

    render_footer()


render()
