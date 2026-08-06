"""P4: 舆情→逻辑链适配器测试。"""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.adapters.sentiment_to_logic_adapter import (
    sentiment_to_logic_chain, logic_chain_to_hypothesis,
)

def test_rule_path_policy():
    r = sentiment_to_logic_chain("低空经济政策发布", use_llm=False)
    assert r["chain"], "逻辑链不能为空"
    assert r["source"] == "rule"
    assert r["beneficiaries"], "政策类应识别受益方"

def test_rule_path_negative():
    r = sentiment_to_logic_chain("某公司因违规被立案调查", use_llm=False)
    assert "风险" in r["impact"] or "承压" in r["impact"]

def test_rule_fallback_unknown():
    r = sentiment_to_logic_chain("完全随机舆情xyz", use_llm=False)
    assert r["chain"], "未知文本也应有兜底链"
    assert r["source"] == "rule_fallback"

def test_empty_text():
    r = sentiment_to_logic_chain("", use_llm=False)
    assert r["chain"], "空文本不崩溃"

def test_to_hypothesis():
    r = sentiment_to_logic_chain("新能源销量增长", use_llm=False)
    h = logic_chain_to_hypothesis(r)
    assert h["core_logic"], "假设核心逻辑不能为空"
    assert h["propagation_path"], "传播路径不能为空"

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
