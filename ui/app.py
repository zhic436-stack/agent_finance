# -*- coding: utf-8 -*-
"""多视角金融研究智能体主应用。"""
from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="多视角金融研究智能体",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.components.styles import inject_theme

inject_theme()

# Auto-load demo data on first visit so all pages have data immediately
if "analysis_result" not in st.session_state:
    try:
        from src.pipeline import load_demo_state
        demo = load_demo_state("低空经济")
        if demo:
            st.session_state["analysis_result"] = demo
            st.session_state["current_topic"] = "低空经济"
            st.session_state["auto_loaded_demo"] = True
    except Exception:
        pass  # Silently skip if demo data can't load

_PAGE_PATH = "pages"

event_page = st.Page(f"{_PAGE_PATH}/1_\u4e8b\u4ef6\u5206\u6790.py", title="事件分析")
factor_page = st.Page(f"{_PAGE_PATH}/2_\u591a\u56e0\u5b50\u5206\u6790.py", title="多因子分析")
risk_page = st.Page(f"{_PAGE_PATH}/3_\u98ce\u9669\u5206\u6790.py", title="风险分析")
report_page = st.Page(f"{_PAGE_PATH}/4_\u7814\u7a76\u62a5\u544a.py", title="研究报告")
history_page = st.Page(f"{_PAGE_PATH}/5_\u5386\u53f2\u8bb0\u5f55.py", title="历史记录")
backtest_page = st.Page(f"{_PAGE_PATH}/6_\u56de\u6d4b.py", title="策略回测")
optimize_page = st.Page(f"{_PAGE_PATH}/8_\u7ec4\u5408\u4f18\u5316.py", title="组合优化")

pg = st.navigation(
    {
        "分析工具": [event_page, factor_page, risk_page, backtest_page],
        "研究成果": [report_page, history_page],
        "组合工具": [optimize_page],
    },
)

with st.sidebar:
    st.markdown("""<div style="padding:8px 0 12px 0">
      <div style="font-size:1.15em;font-weight:700;letter-spacing:-0.01em;
                  background:linear-gradient(135deg,#3b82f6,#8b5cf6);
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                  background-clip:text;">
        多视角金融研究智能体
      </div>
      <div style="font-size:0.72em;color:#64748b;margin-top:4px;letter-spacing:0.04em;text-transform:uppercase;">
        华为昇腾 × AtomGit AI 金融应用黑客松
      </div>
      <div style="margin-top:10px;display:flex;gap:6px;">
        <span class="badge badge-blue" style="font-size:0.7em;">v1.0</span>
        <span class="badge badge-purple" style="font-size:0.7em;">金融智能体</span>
      </div>
    </div>""", unsafe_allow_html=True)
    st.divider()
    # 当前分析来源状态徽章
    _result = st.session_state.get("analysis_result") or {}
    _topic = st.session_state.get("current_topic", "尚未加载主题")
    if st.session_state.get("auto_loaded_demo") or _result.get("_from_demo"):
        st.markdown('<span class="badge badge-blue" style="font-size:0.72em;">📊 演示数据</span>', unsafe_allow_html=True)
        st.caption("已加载「" + _topic + "」预计算分析")
    elif _result.get("_from_agent"):
        st.markdown('<span class="badge badge-purple" style="font-size:0.72em;">🤖 Agent 自主研究</span>', unsafe_allow_html=True)
        st.caption("📍 " + _topic + "")
    else:
        st.markdown('<span class="badge badge-green" style="font-size:0.72em;">📈 实时分析</span>', unsafe_allow_html=True)
        st.caption("📍 " + _topic + "")
    if st.session_state.get("analysis_elapsed"):
        st.caption("⏱️ 耗时 " + str(round(st.session_state.get("analysis_elapsed", 0) / 1000, 1)) + " 秒")

pg.run()
