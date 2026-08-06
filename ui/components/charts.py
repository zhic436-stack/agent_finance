# -*- coding: utf-8 -*-
"""本地 Plotly 图表组件。"""

import plotly.graph_objects as go
import streamlit as st
from typing import Optional, List, Dict, Any

_FONT = {"color": "#f8fafc", "family": "Microsoft YaHei, sans-serif"}
_TITLE_FONT = {"color": "#f8fafc", "family": "Microsoft YaHei, sans-serif", "size": 16}


def _render_plotly(figure: go.Figure, height: int = 400) -> None:
    figure.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=_FONT,
        margin={"l": 35, "r": 20, "t": 55, "b": 35},
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def render_factor_radar(stock_name: str, scores: List[float], labels: Optional[List[str]] = None) -> None:
    if labels is None:
        labels = ["事件因子", "价值因子", "成长因子", "市场因子"]

    values = list(scores)
    figure = go.Figure(
        go.Scatterpolar(
            r=values + values[:1],
            theta=labels + labels[:1],
            fill="toself",
            line={"color": "#3b82f6", "width": 2},
            fillcolor="rgba(59,130,246,0.25)",
            name=stock_name,
        )
    )
    figure.update_layout(
        title={"text": f"{stock_name} 四因子雷达", "font": _TITLE_FONT},
        showlegend=False,
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
    )
    _render_plotly(figure)


def render_risk_pie(risk_counts: Dict[str, int]) -> None:
    color_map = {"低": "#22c55e", "中": "#f59e0b", "高": "#ef4444", "数据暂缺": "#64748b"}
    labels = [key for key, value in risk_counts.items() if value]
    values = [risk_counts[key] for key in labels]
    if not values:
        st.info("暂无可展示的风险分布数据。")
        return

    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker={"colors": [color_map.get(key, "#64748b") for key in labels]},
            textinfo="label+value+percent",
            hovertemplate="风险等级：%{label}<br>股票数量：%{value}<br>占比：%{percent}<extra></extra>",
        )
    )
    figure.update_layout(title={"text": "风险等级分布", "font": _TITLE_FONT})
    _render_plotly(figure)


def render_factor_bar(data: List[Dict[str, Any]], title: str = "四因子对比") -> None:
    factor_names = ["事件因子", "价值因子", "成长因子", "市场因子"]
    stocks = [item.get("股票", "") for item in data]

    figure = go.Figure()
    for factor_name in factor_names:
        figure.add_trace(
            go.Bar(
                name=factor_name,
                x=stocks,
                y=[item.get(factor_name, 0) for item in data],
                hovertemplate=f"{factor_name}：%{{y:.1f}}<extra></extra>",
            )
        )
    figure.update_layout(
        title={"text": title, "font": _TITLE_FONT},
        barmode="group",
        yaxis={"range": [0, 100], "title": "得分"},
    )
    _render_plotly(figure, height=420)


def render_heatmap(data: List[List[float]], x_labels: Optional[List[str]] = None,
                   y_labels: Optional[List[str]] = None, title: str = "因子热力图") -> None:
    figure = go.Figure(
        go.Heatmap(
            z=data,
            x=x_labels,
            y=y_labels,
            zmin=0,
            zmax=100,
            colorscale=[[0, "#1e3a5f"], [0.35, "#3b82f6"], [0.6, "#22c55e"], [0.8, "#f59e0b"], [1, "#ef4444"]],
            hovertemplate="横轴：%{x}<br>纵轴：%{y}<br>得分：%{z:.1f}<extra></extra>",
        )
    )
    figure.update_layout(title={"text": title, "font": _TITLE_FONT})
    _render_plotly(figure)


def render_composite_ranking(data: List[Dict[str, Any]]) -> None:
    rows = sorted(data, key=lambda item: item.get("综合得分", 0), reverse=True)[:10]
    rows = list(reversed(rows))
    figure = go.Figure(
        go.Bar(
            x=[item.get("综合得分", 0) for item in rows],
            y=[item.get("股票", "") for item in rows],
            orientation="h",
            marker={"color": "#3b82f6"},
            hovertemplate="综合得分：%{x:.1f}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": "综合得分前十", "font": _TITLE_FONT},
        xaxis={"range": [0, 100], "title": "综合得分"},
    )
    _render_plotly(figure, height=420)


def render_ranking_bar(data: List[Dict[str, Any]], top_n: int = 10) -> None:
    rows = sorted(data, key=lambda item: item.get("composite", 0), reverse=True)[:top_n]
    rows = list(reversed(rows))
    figure = go.Figure(
        go.Bar(
            x=[item.get("composite", 0) for item in rows],
            y=[item.get("name", "未知股票") for item in rows],
            orientation="h",
            marker={"color": "#3b82f6"},
            hovertemplate="综合得分：%{x:.1f}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": "综合得分排名", "font": _TITLE_FONT},
        xaxis={"range": [0, 100], "title": "综合得分"},
    )
    _render_plotly(figure, height=420)
