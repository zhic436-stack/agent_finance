# -*- coding: utf-8 -*-
"""风险分析页面。"""
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


RISK_ORDER = ["高", "中", "低", "数据暂缺"]
RISK_COLORS = {
    "高": "#ef4444",
    "中": "#f59e0b",
    "低": "#22c55e",
    "数据暂缺": "#64748b",
}
VALUATION_LABELS = {
    "高": "估值偏高",
    "中": "估值适中",
    "低": "估值偏低",
    "数据暂缺": "数据暂缺",
}


def _format_percent(value):
    return "数据暂缺" if value is None else f"{float(value):.2%}"


def _normalized_level(value):
    text = str(value or "数据暂缺")
    aliases = {
        "high": "高",
        "medium": "中",
        "mid": "中",
        "low": "低",
        "unknown": "数据暂缺",
    }
    return aliases.get(text.lower(), text if text in RISK_ORDER else "数据暂缺")


def _risk_detail(risk):
    return (
        f"年化波动率 {_format_percent(risk.get('volatility'))}；"
        f"最大回撤 {_format_percent(risk.get('max_drawdown'))}"
    )


def _build_rows(stock_results):
    rows = []
    for item in stock_results:
        stock = item.get("stock")
        risk = item.get("risk", {})
        level = _normalized_level(risk.get("risk_level"))
        valuation = _normalized_level(risk.get("valuation_risk"))
        rows.append({
            "股票名称": getattr(stock, "name", ""),
            "股票代码": getattr(stock, "code", ""),
            "风险等级": level,
            "年化波动率": _format_percent(risk.get("volatility")),
            "最大回撤": _format_percent(risk.get("max_drawdown")),
            "估值状态": VALUATION_LABELS.get(valuation, "数据暂缺"),
            "风险说明": _risk_detail(risk),
        })
    return rows


def _render_distribution(counts):
    labels = [level for level in RISK_ORDER if counts.get(level, 0) > 0]
    values = [counts[level] for level in labels]
    if not values:
        st.info("暂无可展示的风险分布数据。")
        return

    figure = go.Figure(
        data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.58,
            sort=False,
            marker={"colors": [RISK_COLORS[level] for level in labels]},
            textinfo="label+value+percent",
            textfont={"color": "#f8fafc", "size": 14},
            hovertemplate="风险等级：%{label}<br>股票数量：%{value}<br>占比：%{percent}<extra></extra>",
        )]
    )
    figure.update_layout(
        height=390,
        margin={"l": 20, "r": 20, "t": 25, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#f8fafc", "family": "Microsoft YaHei, sans-serif"},
        legend={"orientation": "h", "y": -0.08, "x": 0.5, "xanchor": "center"},
        annotations=[{
            "text": f"共 {sum(values)} 只",
            "x": 0.5,
            "y": 0.5,
            "showarrow": False,
            "font": {"size": 20, "color": "#f8fafc"},
        }],
    )
    figure.update_layout(
        height=390,
        margin={"l": 20, "r": 20, "t": 25, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#f8fafc", "family": "Microsoft YaHei, sans-serif"},
        legend={"orientation": "h", "y": -0.08, "x": 0.5, "xanchor": "center"},
        annotations=[{
            "text": f"共 {sum(values)} 只",
            "x": 0.5,
            "y": 0.5,
            "showarrow": False,
            "font": {"size": 20, "color": "#f8fafc"},
        }],
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def render():
    st.title("风险分析")
    if (st.session_state.get("analysis_result") or {}).get("_from_demo"):
        st.caption("说明：当前展示离线缓存的预计算结果（演示数据，非实时行情）。")

    st.caption("查看风险分布、分级股票清单、波动率、最大回撤与估值状态。")

    result = st.session_state.get("analysis_result")
    if not result:
        st.info("暂无分析数据，请先在事件分析页面运行一次分析。")
        render_footer()
        return

    stock_results = result.get("stock_results", [])
    if not stock_results:
        st.warning("当前分析结果没有股票数据。")
        render_footer()
        return

    rows = _build_rows(stock_results)
    counts = {level: sum(row["风险等级"] == level for row in rows) for level in RISK_ORDER}

    st.markdown("### 风险分布")
    chart_col, summary_col = st.columns([1.5, 1])
    with chart_col:
        _render_distribution(counts)
    with summary_col:
        st.markdown("#### 风险概览")
        metric_cols = st.columns(2)
        for index, level in enumerate(RISK_ORDER):
            with metric_cols[index % 2]:
                st.metric(f"{level}风险" if level != "数据暂缺" else "数据暂缺", counts[level])
        st.info("点击下方风险等级即可查看对应股票，不再只显示高风险股票。")

    st.markdown("### 分级股票清单")
    available_levels = ["全部"] + [level for level in RISK_ORDER if counts[level] > 0]
    selected_level = st.segmented_control(
        "风险等级筛选",
        available_levels,
        default="全部",
        key="risk_level_filter",
    )
    visible_rows = rows if selected_level in (None, "全部") else [
        row for row in rows if row["风险等级"] == selected_level
    ]
    st.caption(f"当前显示 {len(visible_rows)} 只股票")

    for level in RISK_ORDER:
        level_rows = [row for row in visible_rows if row["风险等级"] == level]
        if not level_rows:
            continue
        with st.expander(f"{level}风险（{len(level_rows)}只）", expanded=level == selected_level or selected_level in (None, "全部")):
            for row in level_rows:
                st.markdown(
                    f"**{row['股票名称']}（{row['股票代码']}）**　"
                    f"年化波动率 {row['年化波动率']}　|　最大回撤 {row['最大回撤']}　|　{row['估值状态']}"
                )

    st.markdown("### 风险明细表")
    table = pd.DataFrame(visible_rows)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "股票名称": st.column_config.TextColumn("股票名称", width="medium"),
            "股票代码": st.column_config.TextColumn("股票代码", width="small"),
            "风险等级": st.column_config.TextColumn("风险等级", width="small"),
            "年化波动率": st.column_config.TextColumn("年化波动率", width="small"),
            "最大回撤": st.column_config.TextColumn("最大回撤", width="small"),
            "估值状态": st.column_config.TextColumn("估值状态", width="small"),
            "风险说明": st.column_config.TextColumn("风险说明", width="large"),
        },
    )

    render_footer()


render()
import plotly.graph_objects as go
