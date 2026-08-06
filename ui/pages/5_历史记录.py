# -*- coding: utf-8 -*-
"""History Page."""
from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.components.footer import render_footer


def _display_topic(topic: str) -> str:
    aliases = {
        "Low-altitude Economy": "低空经济",
    }
    return aliases.get(topic, topic)


def render():
    st.title("分析历史")
    st.caption("查看历史分析记录，并重新加载分析结果。")

    from src.history_manager import list_history, load_history

    records = list_history(limit=20)
    if not records:
        st.info("暂无历史记录，请先运行一次分析。")
        render_footer()
        return

    st.markdown(f"**共 {len(records)} 条记录**")
    for i, rec in enumerate(records):
        label = f"**{_display_topic(rec['topic'])}** - {rec['time']}（{rec['elapsed_ms']} 毫秒）"
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(label)
            with col2:
                if st.button("加载", key=f"hist_{i}", width="stretch"):
                    result = load_history(rec["path"])
                    if result:
                        st.session_state["analysis_result"] = result
                        st.session_state["current_topic"] = result.get("topic", rec["topic"])
                        st.session_state["analysis_elapsed"] = result.get("elapsed_ms", 0)
                        st.toast(f"已加载：{rec['topic']}")
                        st.rerun()
                    else:
                        st.error("该记录加载失败。")

    st.markdown("---")
    confirm = st.checkbox("我已确认要删除全部历史记录（不可恢复）", key="confirm_clear_history")
    if st.button("清空全部历史", type="secondary", width="stretch", disabled=not confirm):
        import shutil
        from src.history_manager import HISTORY_DIR
        try:
            if HISTORY_DIR.exists():
                shutil.rmtree(HISTORY_DIR)
                st.success("历史记录已清空。")
                st.rerun()
        except OSError as e:
            st.error(f"操作失败：{e}")

    render_footer()


render()
