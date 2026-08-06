# -*- coding: utf-8 -*-
"""orchestrator ReAct 编排器单元测试 (mock LLM, 离线确定性)。"""
import json

import pytest

import src.llm as llm_mod


def _mock_final_json():
    return {
        "summary": "测试结论",
        "event": {"topic": "低空经济", "event_type": "政策", "benefited_industries": ["低空"], "keywords": ["低空"]},
        "chain": [{"name": "整机制造", "position": "中游", "transmission": "政策驱动"}],
        "concepts": ["低空经济"],
        "key_stocks": [
            {"code": "920961", "name": "测试A", "rationale": "受益", "risk_level": "中",
             "factors": {"event": 80, "value": 50, "growth": 60, "market": 70, "composite": 66}},
        ],
        "risk_notes": "注意波动",
        "report_md": "# 测试报告\n\n> 免责声明",
    }


def _make_react_mock(monkeypatch):
    """mock: 第一轮调用 get_concept_stocks, 第二轮输出 final JSON。"""
    calls = {"n": 0}

    def fake(messages, tools=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"content": "先查成分股", "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "get_concept_stocks", "arguments": json.dumps({"concept": "低空经济"})},
            }]}
        return {"content": json.dumps(_mock_final_json()), "tool_calls": []}

    monkeypatch.setattr(llm_mod, "chat_completion_with_tools", fake)
    return calls


def test_react_loop_success(monkeypatch):
    from src.orchestrator import run_agent_research
    _make_react_mock(monkeypatch)
    r = run_agent_research("低空经济", max_steps=4, use_llm=True)
    assert r["ok"] is True
    assert r["_from_agent"] is True
    assert r["event"]["event_type"] == "政策"
    assert len(r["stock_results"]) == 1
    assert r["stock_results"][0]["factors"]["composite"] == 66.0
    assert "免责声明" in r["report"]
    assert any("get_concept_stocks" in t["step"] for t in r["trace"]), "应记录工具调用轨迹"


def test_step_limit_protection(monkeypatch):
    from src.orchestrator import run_agent_research
    calls = {"n": 0}

    def endless(messages, tools=None, **kw):
        calls["n"] += 1
        return {"content": "继续", "tool_calls": [{
            "id": f"call_{calls['n']}", "type": "function",
            "function": {"name": "list_offline_topics", "arguments": "{}"},
        }]}

    monkeypatch.setattr(llm_mod, "chat_completion_with_tools", endless)
    r = run_agent_research("低空经济", max_steps=3, use_llm=True)
    # 步数上限保护: 无限工具循环必须在有限步内结束, 不挂起; 且有总结降级产出
    assert calls["n"] <= 3 + 1, "LLM 调用次数不应超过 max_steps + 1 (总结轮)"
    assert isinstance(r, dict) and "ok" in r
    assert r.get("trace") is not None


def test_report_fallback_when_json_invalid(monkeypatch):
    from src.orchestrator import run_agent_research
    calls = {"n": 0}

    def fake(messages, tools=None, **kw):
        calls["n"] += 1
        if calls["n"] <= 2:
            return {"content": "查数据", "tool_calls": [{
                "id": f"call_{calls['n']}", "type": "function",
                "function": {"name": "get_stock_market_data", "arguments": json.dumps({"code": "920961"})},
            }]}
        # 最后一轮总结: 输出非 JSON 文本 -> 应降级为报告模式
        return {"content": "# 低空经济研究报告\n\n研究过程摘要…\n\n> 免责声明", "tool_calls": []}

    monkeypatch.setattr(llm_mod, "chat_completion_with_tools", fake)
    r = run_agent_research("低空经济", max_steps=3, use_llm=True)
    assert r["ok"] is True, "JSON 解析失败应降级为报告模式"
    assert r.get("_report_only") is True
    assert "免责声明" in r["report"]
    # 报告模式: 有产出且不抛异常 (股票列表可能为空, 取决于工具结果)


def test_llm_none_fallback(monkeypatch):
    from src.orchestrator import run_agent_research
    calls = {"n": 0}

    def fake(messages, tools=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"content": "查", "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "list_offline_topics", "arguments": "{}"},
            }]}
        return None  # 中间轮失败

    monkeypatch.setattr(llm_mod, "chat_completion_with_tools", fake)
    r = run_agent_research("低空经济", max_steps=3, use_llm=True)
    # 失败后应尝试总结降级; 若总结也失败则 ok=False 且不抛异常
    assert isinstance(r, dict)
    assert "ok" in r
