# -*- coding: utf-8 -*-
"""Portfolio Optimization Page."""
import sys
from pathlib import Path
import streamlit as st
import numpy as np

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.components.footer import render_footer



def render():
    st.title("组合优化")
    st.caption("使用层次风险平价、最大夏普或最小波动方法构建投资组合。")

    result = st.session_state.get("analysis_result")
    if result is None or not result.get("stock_results"):
        st.info("暂无分析数据，请先运行事件分析。")
        render_footer()
        return

    ranked = sorted(
        result["stock_results"],
        key=lambda r: r.get("factors", {}).get("composite", 0),
        reverse=True,
    )

    selected = ranked[:6]
    codes = [r["stock"].code for r in selected if r.get("stock")]
    names = [r["stock"].name for r in selected if r.get("stock")]

    st.markdown(f"**已选股票：** {', '.join(names)}")

    if result.get("_from_demo"):
        st.warning("当前为预计算演示数据，缺少可核验的历史行情，组合优化已禁用。请先运行真实事件分析。")
        render_footer()
        return

    strategy = st.selectbox(
        "优化方法",
        ["hrp", "max_sharpe", "min_volatility"],
        format_func=lambda s: {
            "hrp": "层次风险平价（HRP）",
            "max_sharpe": "最大夏普比率",
            "min_volatility": "最小波动率",
        }.get(s, s),
    )

    if st.button("开始优化", type="primary", width="stretch"):
        from src.adapters.portfolio_adapter import optimize_portfolio
        from src.real_covariance import compute_covariance_matrix, compute_expected_returns

        with st.spinner("正在拉取真实行情并计算组合..."):
            covariance = compute_covariance_matrix(codes)
            expected_returns = None
            data_error = None
            if covariance is None:
                data_error = "真实协方差数据暂缺，无法生成可信组合。"
            elif strategy == "max_sharpe":
                returns_by_code = compute_expected_returns(codes)
                missing_codes = [code for code in codes if code not in returns_by_code]
                if missing_codes:
                    data_error = "以下股票缺少真实收益数据：" + ", ".join(missing_codes)
                else:
                    expected_returns = [returns_by_code[code] for code in codes]

            if data_error:
                st.error(data_error)
            else:
                optimization = optimize_portfolio(
                    codes,
                    expected_returns=expected_returns,
                    cov_matrix=covariance,
                    method=strategy,
                )
                if not optimization.get("ok"):
                    st.error(f"组合优化失败：{optimization.get('error', '未知错误')}")
                else:
                    weights = optimization["weights"]
                    st.success(f"组合优化完成，权重合计 {optimization.get('sum_weights', 1.0):.2%}。")
                    st.markdown("### 组合权重")
                    weight_data = [
                        {"code": code, "name": name, "weight_pct": weights.get(code, 0) * 100}
                        for code, name in zip(codes, names)
                    ]
                    st.dataframe(
                        weight_data,
                        column_config={
                            "code": "股票代码",
                            "name": "股票名称",
                            "weight_pct": st.column_config.NumberColumn("权重（%）", format="%.1f%%"),
                        },
        width="stretch",
                        hide_index=True,
                    )
    render_footer()


render()
# REAL_COV_INTEGRATED
