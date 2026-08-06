# -*- coding: utf-8 -*-
"""Enterprise widgets: AG Grid tables + 3D data cards.
Sources: ag-grid.com (via st-aggrid), ui.aceternity.com (3D cards).
"""
from html import escape

import streamlit as st
import pandas as pd

try:  # st-aggrid 为可选增强依赖; 环境缺失时降级为原生表格
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
    _HAS_AGGRID = True
except Exception:  # noqa: BLE001
    AgGrid = GridOptionsBuilder = GridUpdateMode = JsCode = None
    _HAS_AGGRID = False


def render_risk_table(data: list, key="risk_table"):
    """Enterprise data table with sort/filter/color markers."""
    df = pd.DataFrame(data)
    if not _HAS_AGGRID:
        # 降级: 无 st-aggrid 环境用原生表格
        st.dataframe(df, use_container_width=True)
        return None
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        sortable=True, filter=True, resizable=True,
        minWidth=80, flex=1
    )
    risk_js = JsCode("""
function(params) {
  var val = params.value;
  var color = val === '\u9ad8' ? '#ef4444' : val === '\u4e2d' ? '#f59e0b' : '#22c55e';
  return '<span style="display:inline-block;padding:2px 10px;border-radius:12px;background:'+color+'22;color:'+color+';font-weight:600;font-size:0.85em;">'+val+'</span>';
}
""")
    if "risk_level" in df.columns:
        gb.configure_column("risk_level", cellRenderer=risk_js)
    if "risk" in df.columns:
        pass
    gb.configure_grid_options(
        rowStyle={"background": "transparent"},
        headerHeight=44, rowHeight=40
    )
    grid = AgGrid(
        df, gridOptions=gb.build(),
        update_mode=GridUpdateMode.NO_UPDATE,
        allow_unsafe_jscode=True, key=key,
        height=min(400, 44 * (len(data) + 1)),
    )
    return grid


def render_data_card_3d(title, metric, subtitle="", color="#3b82f6"):
    """3D data card - Aceternity UI pattern."""
    title, metric, subtitle = escape(str(title)), escape(str(metric)), escape(str(subtitle))
    return f'''
<div class="data-card-3d" style="text-align:center;margin:8px;">
  <div style="font-size:2em;font-weight:800;color:{color};">{metric}</div>
  <div style="font-weight:600;color:var(--text-primary);">{title}</div>
  <div style="font-size:0.8em;color:var(--text-secondary);">{subtitle}</div>
</div>'''

