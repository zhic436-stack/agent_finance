# -*- coding: utf-8 -*-
"""Research Report Page."""
from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.components.footer import render_footer
from ui.components.widgets import render_data_card_3d
from ui.components.cards import render_stock_table, render_factor_card


def _export_filename(topic: str, ext: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in topic if c not in '\\/:*?"<>|')[:30] or "report"
    return f"{safe}_{ts}.{ext}"


def render():
    st.title("研究报告")
    st.caption("查看分析结论，并导出文本报告或结构化数据。")

    result = st.session_state.get("analysis_result")
    if result is None:
        st.info("暂无分析数据，请先运行事件分析。")
        render_footer()
        return

    report = result.get("report", "")
    if not report:
        st.warning("尚未生成研究报告。")
        render_footer()
        return

    st.markdown(report)  # 默认转义 HTML, 防 LLM/用户输入注入

    st.markdown("---")
    st.markdown("### 导出报告")
    topic = result.get("topic", "")
    md_name = _export_filename(topic, "md")
    json_name = _export_filename(topic, "json")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "下载文本报告（.md）",
            data=report.encode("utf-8"),
            file_name=md_name,
            mime="text/markdown",
            width="stretch",
        )
    with col2:
        json_data = {
            "topic": result.get("topic", ""),
            "event": result.get("event", {}),
            "chain": result.get("chain", []),
            "concepts": result.get("concepts", []),
            "report": report,
            "elapsed_ms": result.get("elapsed_ms", 0),
            "stock_results": [
                {
                    "code": r.get("stock").code if hasattr(r.get("stock", {}), "code") else r.get("stock", {}).get("code", ""),
                    "name": r.get("stock").name if hasattr(r.get("stock", {}), "name") else r.get("stock", {}).get("name", ""),
                    "factors": r.get("factors", {}),
                    "risk": r.get("risk", {}),
                }
                for r in result.get("stock_results", [])
            ],
        }
        st.download_button(
            "下载结构化数据（.json）",
            data=json.dumps(json_data, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=json_name,
            mime="application/json",
            width="stretch",
        )

    if result.get("_from_demo"):
        st.caption("说明：当前展示离线缓存的预计算结果。")
    elif result.get("_from_agent"):
        st.caption("说明：本报告由 Agent 自主调用金融工具生成（研究轨迹见事件分析页）。")

    render_footer()


render()
