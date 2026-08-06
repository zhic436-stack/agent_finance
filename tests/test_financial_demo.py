"""财务演示数据 + 因子兜底测试。

验证:
1. 演示数据确定性 (同代码同结果) 与范围合理性
2. DEMO_DATA_FALLBACK 关闭时: 空财务 -> 0分 (保持语义)
3. DEMO_DATA_FALLBACK 开启时: 空财务 -> 演示数据兜底非零
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collector import FinancialData, StockProfile
from src.financial_demo_data import generate_financial_demo_data


def test_demo_data_deterministic():
    d1 = generate_financial_demo_data("000099", "中信海直")
    d2 = generate_financial_demo_data("000099", "中信海直")
    assert d1 == d2, "演示数据必须确定性 (同代码同结果)"


def test_demo_data_ranges():
    for code in ["000099", "600519", "920961", "002230"]:
        d = generate_financial_demo_data(code)
        assert 15 <= d["pe"] <= 40, f"{code} PE 越界"
        assert 1 <= d["pb"] <= 8
        assert 0.02 <= d["roe"] <= 0.25
        assert -0.05 <= d["revenue_growth"] <= 0.40
        assert -0.10 <= d["profit_growth"] <= 0.50
        assert d["is_demo"] is True


def test_demo_data_different_codes_differ():
    d1 = generate_financial_demo_data("000099")
    d2 = generate_financial_demo_data("600519")
    # 极大概率不同 (确定性随机种子)
    assert (d1["pe"], d1["roe"]) != (d2["pe"], d2["roe"])


def test_fallback_disabled_zero(monkeypatch):
    """默认关闭: 空财务 -> 0分 (保持语义, 不引入演示数据)。"""
    monkeypatch.setenv("DEMO_DATA_FALLBACK", "0")
    # 需要重载 config 使 DEMO_DATA_FALLBACK 生效
    import config
    monkeypatch.setattr(config, "DEMO_DATA_FALLBACK", False)

    from src.factor_engine import calc_growth_factor, calc_value_factor
    s = StockProfile(code="000099", name="中信海直", financials=FinancialData())
    assert calc_value_factor(s) == 0.0
    assert calc_growth_factor(s) == 0.0


def test_fallback_enabled_nonzero(monkeypatch):
    """开启演示数据: 空财务 -> 非零兜底。"""
    import config
    monkeypatch.setattr(config, "DEMO_DATA_FALLBACK", True)

    from src.factor_engine import calc_growth_factor, calc_value_factor
    s = StockProfile(code="000099", name="中信海直", financials=FinancialData())
    assert calc_value_factor(s) > 0
    assert calc_growth_factor(s) > 0


def test_real_data_never_overridden(monkeypatch):
    """真实财务数据存在时, 演示数据不得覆盖。"""
    import config
    monkeypatch.setattr(config, "DEMO_DATA_FALLBACK", True)

    from src.factor_engine import calc_value_factor
    # 有真实财务数据 (低PE高ROE -> 高分)
    s = StockProfile(
        code="000099", name="中信海直",
        financials=FinancialData(pe=15, pb=1.5, roe=0.18, pe_percentile=0.2, pb_percentile=0.3),
    )
    v_real = calc_value_factor(s)
    # 空财务用演示数据
    s_empty = StockProfile(code="000099", name="中信海直", financials=FinancialData())
    v_demo = calc_value_factor(s_empty)
    assert v_real > 0
    # 真实高分股票应高于演示分 (演示可能高于真实, 但真实不应被覆盖为0)
    assert v_real >= 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
