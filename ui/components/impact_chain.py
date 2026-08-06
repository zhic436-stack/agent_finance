#
# -*- coding: utf-8 -*-
"""Industry chain display component."""
from __future__ import annotations
from typing import Any, Dict, List
import streamlit as st

try:
    import graphviz
    _HAS_GRAPHVIZ = True
except ImportError:
    _HAS_GRAPHVIZ = False


def render_impact_chain(chain_data: List[Dict[Any, Any]], title: str = "产业链传导路径") -> None:
    """Render industry chain propagation path."""
    if not chain_data:
        st.info("暂无产业链数据")
        return

    st.markdown(f"### {title}")

    if _HAS_GRAPHVIZ:
        try:
            dot = graphviz.Digraph()
            dot.attr(rankdir="LR")
            for i, node in enumerate(chain_data):
                name = node.get("name", "") if isinstance(node, dict) else str(node)
                dot.node(str(i), name)
                if i > 0:
                    dot.edge(str(i - 1), str(i))
            st.graphviz_chart(dot)
            return
        except Exception as e:
            st.caption(f"图形渲染失败，已切换文本模式：{str(e)[:40]}")

    chain_str = " -> ".join(
        (n.get("name", "") if isinstance(n, dict) else str(n)) for n in chain_data
    )
    st.markdown(f"**{title}**: {chain_str}")

    with st.expander("详细信息", expanded=False):
        for node in chain_data:
            if isinstance(node, dict) and node.get("description"):
                st.caption(f"* {node.get('name', '')}: {node.get('description', '')}")
