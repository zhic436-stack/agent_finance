"""事件逻辑因子测试 (B3): 事件强度/产业链位置/逻辑确定性。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collector import StockInfo
from src.factor_engine import (
    calc_chain_position,
    calc_event_strength,
    calc_logic_certainty,
    compute_all_factors,
)

POLICY_EVENT = {
    "topic": "国务院发布低空经济指导意见",
    "event_type": "政策利好",
    "benefited_industries": ["低空经济"],
    "keywords": ["低空经济", "eVTOL"],
}
CONCEPT_EVENT = {"topic": "机器人概念", "event_type": "行业", "benefited_industries": [], "keywords": ["机器人"]}


def make_stock(concepts):
    s = StockInfo(code="000099", name="测试")
    s.concepts = concepts
    return s


def test_event_strength_range():
    assert 0 <= calc_event_strength(POLICY_EVENT) <= 100
    assert calc_event_strength({}) == 50.0  # 空事件中性


def test_chain_position_direct():
    """概念直接命中受益行业 -> 100。"""
    s = make_stock(["低空经济"])
    assert calc_chain_position(s, POLICY_EVENT) == 100.0


def test_chain_position_indirect():
    """概念含关键词 -> 70。"""
    s = make_stock(["eVTOL概念"])
    assert calc_chain_position(s, POLICY_EVENT) == 70.0


def test_chain_position_sentiment():
    """仅相关 -> 30。"""
    s = make_stock(["军工概念"])
    assert calc_chain_position(s, POLICY_EVENT) == 30.0


def test_logic_certainty_levels():
    assert calc_logic_certainty({"topic": "发布XXX", "event_type": "政策"}) == 90.0
    assert calc_logic_certainty({"topic": "规划XXX", "event_type": "政策"}) == 60.0
    assert calc_logic_certainty({"topic": "概念股", "event_type": "行业"}) == 30.0


def test_compute_all_includes_event_logic():
    s = make_stock(["低空经济"])
    f = compute_all_factors(s, POLICY_EVENT)
    for key in ("event_strength", "chain_position", "logic_certainty", "event_logic_composite"):
        assert key in f, f"缺事件逻辑因子 {key}"
        assert 0 <= f[key] <= 100


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
