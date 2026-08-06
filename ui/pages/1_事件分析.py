from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.components.footer import render_footer
from ui.components.widgets import render_data_card_3d
from ui.components.cards import render_stock_table

TOPICS = ["低空经济", "AI算力", "机器人", "新能源"]

def _run_analysis(topic, agent_mode=False):
    from src.history_manager import save_history
    from src.pipeline import load_demo_state, run_analysis
    try:
        cached = load_demo_state(topic)
        if cached:
            st.session_state["analysis_result"] = cached
            st.session_state["current_topic"] = topic
            st.session_state["analysis_elapsed"] = cached.get("elapsed_ms", 0)
            st.toast("已加载缓存分析结果")
            return
        if agent_mode:
            # Agent 路径: LLM 自主调用工具, 无法预知步骤数, 用 spinner
            with st.spinner("Agent 正在自主研究：" + topic + "（模型将自行决定查询哪些数据）"):
                result = run_analysis(topic, use_llm=True, enrich_market=True, use_agent=True)
        else:
            progress = st.progress(0, text="正在分析：" + topic)
            progress.progress(10, text="步骤 1/4：理解事件并推导产业链...")
            # 开启真实行情补充: 市场因子/风险/技术指标基于真实行情, 而非离线当日涨幅
            result = run_analysis(topic, use_llm=True, enrich_market=True)
            progress.progress(60, text="步骤 2/4：拉取数据并计算因子...")
            progress.progress(85, text="步骤 3/4：执行风险分析...")
            progress.progress(100, text="步骤 4/4：研究报告生成完成")
        st.session_state["analysis_result"] = result
        st.session_state["current_topic"] = topic
        st.session_state["analysis_elapsed"] = result.get("elapsed_ms", 0)
        save_history(result, topic)
    except Exception as e:
        st.error(f"分析失败：{e}")
        st.info("请尝试预置主题，或检查网络连接后重试。")

def render():
    st.title("事件分析")
    st.caption("输入金融热点关键词：智能体自动完成事件理解、产业链推导、候选股分析；开启 Agent 模式则由模型自主调用行情/财务/新闻/风险工具研究。")

    cols = st.columns(len(TOPICS))
    for col, topic in zip(cols, TOPICS):
        with col:
            if st.button(topic, width="stretch", key="topic_" + topic):
                _run_analysis(topic)

    with st.form("event_form"):
        topic = st.text_input(
            "热点关键词",
            value=st.session_state.get("current_topic", ""),
            placeholder="例如：低空经济政策、AI 算力需求"
        )
        agent_mode = st.checkbox(
            "Agent 模式：模型自主调用工具研究（更慢，但展示真实推理过程）",
            value=bool(st.session_state.get("agent_mode", False)),
        )
        st.session_state["agent_mode"] = agent_mode
        submitted = st.form_submit_button("开始分析", type="primary", width="stretch")

    if submitted and topic.strip():
        _run_analysis(topic.strip(), agent_mode=agent_mode)

    if (st.session_state.get("analysis_result") is None
            and st.session_state.get("current_topic")
            and not st.session_state.get("auto_ran")):
        st.session_state["auto_ran"] = True
        _run_analysis(st.session_state["current_topic"])

    result = st.session_state.get("analysis_result")
    if result is None:
        st.info("Enter a hotspot keyword or click a preset topic to begin analysis.")
        render_footer()
        return

    from ui.components.trace import render_trace
    render_trace(result)

    event = result.get("event", {})
    st.markdown("### 事件分析结果")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(render_data_card_3d("事件类型", event.get("event_type", "其他"), color="#3b82f6"), unsafe_allow_html=True)
    with col2:
        st.markdown(render_data_card_3d("受益行业", str(len(event.get("benefited_industries", []))), color="#22c55e"), unsafe_allow_html=True)
    with col3:
        st.markdown(render_data_card_3d("关键词", str(len(event.get("keywords", []))), color="#f59e0b"), unsafe_allow_html=True)

    industries = event.get("benefited_industries", [])
    if industries:
        st.markdown("**受益行业**：" + "、".join(industries))
    else:
        st.warning("暂未识别到受益行业，请使用更具体的关键词或预设主题。")

    keywords = event.get("keywords", [])
    if keywords:
        st.markdown("**关键词**：" + "、".join(keywords))

    chain = result.get("chain", [])
    st.markdown("### 产业链推演")
    if chain:
        from ui.components.impact_chain import render_impact_chain
        render_impact_chain(chain, "产业链传导路径")
        transmission = chain[0].get("transmission", "") if chain else ""
        if transmission:
            st.info("**传导逻辑**：" + transmission)
    else:
        st.warning("暂未匹配到产业链规则，请尝试预设主题。")

    concepts = result.get("concepts", [])
    with st.expander("概念映射详情", expanded=False):
        if concepts:
            st.caption(", ".join(concepts))
        else:
            st.caption("No matching concepts found.")

    if result.get("_from_demo"):
        st.caption("说明：当前展示离线缓存的预计算结果。")

    render_footer()

render()
