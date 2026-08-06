#
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict
import streamlit as st


def render_trace(result: Dict[Any, Any]) -> None:
    event = result.get("event", {})
    chain = result.get("chain", [])
    stock_results = result.get("stock_results", [])
    report = result.get("report", "")
    trace = result.get("trace", [])

    with st.status("智能体正在执行...", expanded=True) as status:
        st.write(f"**分析主题**： {result.get('topic', '')}")

        if trace:
            for t in trace:
                icon = "[完成]" if t.get("status") == "ok" else "[注意]"
                st.write(f"{icon} {t.get('step', '')}: {t.get('detail', '')} ({t.get('elapsed_ms', 0)} 毫秒)")
        else:
            if event:
                st.write(f"[完成] 事件识别：{event.get('event_type', '其他')}")
            if chain:
                st.write(f"[完成] 产业链推演：{len(chain)} 个环节")
            if stock_results:
                st.write(f"[完成] 数据与因子分析：{len(stock_results)} 只股票")
            if report:
                st.write("[完成] 研究报告已生成")

        status.update(label="[完成] 分析完成", state="complete")
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"耗时：{result.get('elapsed_ms', 0)} 毫秒")
        with col2:
            st.caption(f"大模型调用：{result.get('llm_calls', 0)}")

    sources = result.get("data_sources", {})
    if sources:
        src_text = " | ".join(f"{k}:{v}" for k, v in sources.items())
        st.caption(f"数据来源：{src_text}")

    errors = result.get("errors", [])
    if errors:
        with st.expander(f"[注意] {len(errors)} 个降级步骤"):
            for e in errors:
                st.caption(f"- {e}")
