# -*- coding: utf-8 -*-
"""Multi-Factor Analysis Page."""
from __future__ import annotations
import sys
from pathlib import Path
import plotly.graph_objects as go
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.components.footer import render_footer
from ui.components.widgets import render_data_card_3d
from ui.components.charts import render_factor_bar, render_ranking_bar
from ui.components.cards import render_stock_table


def render():
    st.title("多因子分析")
    st.caption("展示最近一次分析的因子得分、综合排名与个股详情。")
    if (st.session_state.get("analysis_result") or {}).get("_from_demo"):
        st.caption("说明：当前展示离线缓存的预计算结果（演示数据，非实时行情）。")
    if (st.session_state.get("analysis_result") or {}).get("_from_agent"):
        st.caption("说明：当前为 Agent 自主研究结果，因子得分为模型估算，仅供参考。")


    result = st.session_state.get("analysis_result")
    if result is None:
        st.info("暂无分析数据，请先运行事件分析。")
        render_footer()
        return

    stock_results = result.get("stock_results", [])
    if not stock_results:
        st.warning("当前分析结果没有股票数据。")
        render_footer()
        return

    ranked = sorted(stock_results, key=lambda r: r.get("factors", {}).get("composite", 0), reverse=True)

    # ---- Top 5 ----
    st.markdown("### 综合排名前五")
    top_cols = st.columns(5)
    top5 = ranked[:5]
    for i, (col, r) in enumerate(zip(top_cols, top5)):
        s = r.get("stock")
        f = r.get("factors", {})
        with col:
            name = s.name if s else ""
            code = s.code if s else ""
            score = round(float(f.get("composite", 0) or 0), 1)
            st.markdown(
                render_data_card_3d(f"#{i+1} {name}", str(score), code, color="#3b82f6"),
                unsafe_allow_html=True,
            )

    # ---- Ranking Chart ----
    st.markdown("### 综合得分排名")
    rows = [
        {"name": r.get("stock").name if r.get("stock") else "", "composite": r.get("factors", {}).get("composite", 0)}
        for r in ranked if r.get("stock")
    ]
    if rows:
        render_ranking_bar(rows, top_n=10)

    # ---- Individual Stock Detail ----
    st.markdown("### 个股详情")
    stock_options = {
        f"{r.get('stock').name} ({r.get('stock').code})": r
        for r in ranked if r.get("stock")
    }
    if stock_options:
        selected_label = st.selectbox("选择股票", list(stock_options.keys()))
        if selected_label:
            sel = stock_options[selected_label]
            st.markdown(f"**{selected_label}**")
            factors = sel.get("factors", {})
            bar_data = [{"股票": "因子", 
                         "事件因子": factors.get("event", 0),
                         "价值因子": factors.get("value", 0),
                         "成长因子": factors.get("growth", 0),
                         "市场因子": factors.get("market", 0)}]
            render_factor_bar(bar_data, title="四因子分解")

            # ---- pandas-ta Technical Indicators (powered by twopirllc/pandas-ta) ----
            st.markdown("---")
            st.markdown("### 技术指标")
            st.caption("展示相对强弱、布林带、均线交叉和能量潮等技术指标。")
            try:
                from src.factor_engine import compute_technical_factors
                stock = sel.get("stock")
                stock_code = stock.code if stock else ""
                closes = list(getattr(getattr(stock, "market", None), "closes", []) or [])
                if len(closes) < 20:
                    st.info("当前股票缺少足够的真实历史行情（实时分析时自动拉取），技术指标暂不展示。")
                else:
                    tech = compute_technical_factors(stock_code, closes)
                    if tech is None:
                        st.info("技术指标依赖或行情格式暂不可用，当前结果不使用模拟数据填充。")
                    else:
                        # Display as metric cards
                        tc1, tc2, tc3, tc4, tc5 = st.columns(5)
                        with tc1:
                            st.metric("趋势（均线）", f"{tech.get('trend', 50):.0f}")
                        with tc2:
                            st.metric("动量（相对强弱）", f"{tech.get('momentum', 50):.0f}")
                        with tc3:
                            st.metric("成交量（能量潮）", f"{tech.get('volume', 50):.0f}")
                        with tc4:
                            st.metric("波动率（布林带）", f"{tech.get('volatility', 50):.0f}")
                        with tc5:
                            st.metric("技术综合分", f"{tech.get('composite', 50):.0f}")
                        tech_labels = ["趋势", "动量", "成交量", "波动率"]
                        tech_values = [tech.get(k, 50) for k in ["trend", "momentum", "volume", "volatility"]]
                        figure = go.Figure(go.Bar(
                            x=tech_values,
                            y=tech_labels,
                            orientation="h",
                            marker={"color": "#22c55e"},
                            hovertemplate="%{y}：%{x:.1f}<extra></extra>",
                        ))
                        figure.update_layout(
                            title="技术因子得分",
                            height=280,
                            margin={"l": 35, "r": 20, "t": 50, "b": 30},
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font={"color": "#f8fafc", "family": "Microsoft YaHei, sans-serif"},
                            xaxis={"range": [0, 100], "title": "得分"},
                        )
                        st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
            except Exception:
                st.caption("技术指标计算失败，请稍后重试。")

    # ---- Full Table ----
    st.markdown("### 全部股票")
    table_rows = [
        {
            "code": r.get("stock").code if r.get("stock") else "",
            "name": r.get("stock").name if r.get("stock") else "",
            "factors": r.get("factors", {}),
            "risk": r.get("risk", {}),
        }
        for r in ranked
    ]
    render_stock_table(table_rows)

    st.caption(f"已分析 {len(ranked)} 只股票。")
    render_footer()


render()
