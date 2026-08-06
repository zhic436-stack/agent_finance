"""卡片组件: streamlit-aggrid 数据表格 (排序/筛选/列宽/风险色标)。

替换 st.dataframe 和手写卡片容器:
- 列排序 / 列筛选 / 列宽拖拽 (AgGrid 内建)
- 风险等级列按颜色标记 (绿/橙/红)
- 固定表头 + 虚拟滚动 (AgGrid 默认)
"""
from __future__ import annotations

from html import escape
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# 风险等级 -> 颜色
_RISK_COLOR = {
    "低": "#2ca02c",
    "中": "#ff7f0e",
    "高": "#d62728",
    "数据暂缺": "#888888",
    "未知": "#888888",
}
_VALUATION_CN = {"低": "低估", "中": "合理", "高": "高估"}
_COMPOSITE_CELL_STYLE = JsCode("""
function(params) {
  return '<span style="color:#1f77b4;font-weight:bold">' + params.value + '</span>';
}
""")

# 风险列颜色渲染 (AgGrid cellRenderer JS, 返回 HTML 字符串避免 React error)
_RISK_CELL_STYLE = JsCode("""
function(params) {
  const colors = {
    '低': '#2ca02c',
    '中': '#ff7f0e',
    '高': '#d62728'
  };
  const c = colors[params.value] || '#888888';
  return '<span style="color:' + c + ';font-weight:bold">' + params.value + '</span>';
}
""")


def render_stock_table(rows: List[Dict[str, Any]]) -> None:
    """股票排名表格: AgGrid 交互表格 (排序/筛选/列宽/风险色标)。

    rows: [{"code", "name", "factors", "risk"}, ...]
    """
    if not rows:
        st.info("暂无股票数据")
        return

    table = []
    for r in rows:
        f = r.get("factors", {})
        risk = r.get("risk", {})
        risk_level = risk.get("risk_level", "未知")
        table.append({
            "代码": r.get("code", ""),
            "名称": r.get("name", ""),
            "事件": round(float(f.get("event", 0) or 0), 1),
            "价值": round(float(f.get("value", 0) or 0), 1),
            "成长": round(float(f.get("growth", 0) or 0), 1),
            "市场": round(float(f.get("market", 0) or 0), 1),
            "综合": round(float(f.get("composite", 0) or 0), 1),
            "风险": risk_level,
            "估值": _VALUATION_CN.get(risk.get("valuation_risk", ""), "未知"),
        })
    df = pd.DataFrame(table)

    gb = GridOptionsBuilder.from_dataframe(df)
    # 所有列可排序/筛选/调整宽度
    for col in df.columns:
        gb.configure_column(col, sortable=True, filter=True, resizable=True)
    # 表格选项: 固定表头 + 虚拟滚动 + 分页
    # 注意: 不加 configure_side_bar / configure_default_column / cellStyle
    #       (st_aggrid 1.2.1 与 streamlit 1.60 不兼容, 触发 React error)
    gb.configure_pagination(paginationAutoPageSize=True)
    grid_options = gb.build()

    AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        allow_unsafe_jscode=True,
        height=420,
        fit_columns_on_grid_load=True,
    )


def render_factor_card(factors: Dict[str, float]) -> None:
    """因子总览 (5 指标并排)。"""
    if not factors:
        st.info("暂无因子数据")
        return
    cols = st.columns(5)
    labels = ["事件", "价值", "成长", "市场", "综合"]
    keys = ["event", "value", "growth", "market", "composite"]
    for col, label, key in zip(cols, labels, keys):
        with col:
            st.metric(label, round(float(factors.get(key, 0) or 0), 1))


def render_stock_card(stock: Any, factors: Dict[str, float], risk: Dict[str, Any]) -> None:
    """单只股票卡 (精简为一行指标, 配合表格使用)。"""
    name = escape(getattr(stock, "name", "") or "")
    code = getattr(stock, "code", "") or ""
    risk_level = risk.get("risk_level", "未知") if risk else "未知"
    color = _RISK_COLOR.get(risk_level, "#888")
    composite = round(float(factors.get("composite", 0) or 0), 1)
    st.markdown(
        f"**{name}** `{code}` — 综合 **{composite}** · "
        f"风险 <span style='color:{color};font-weight:bold'>{risk_level}</span>",
        unsafe_allow_html=True,
    )


def render_risk_badge(risk: Dict[str, Any]) -> str:
    """返回风险等级的 markdown 徽章。"""
    level = risk.get("risk_level", "未知") if risk else "未知"
    color = _RISK_COLOR.get(level, "#888")
    return f"<span style='color:{color};font-weight:bold'>{level}</span>"
