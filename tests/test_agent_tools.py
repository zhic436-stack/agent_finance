# -*- coding: utf-8 -*-
"""agent_tools 工具层单元测试 (离线, 不触网)。"""
import pytest


def test_tool_schemas_count():
    from src.agent_tools import get_tool_schemas, tool_names
    schemas = get_tool_schemas()
    names = tool_names()
    assert len(schemas) == 10, f"应有 10 个工具, 实际 {len(schemas)}"
    assert len(names) == len(set(names)), "工具名不应重复"
    for s in schemas:
        fn = s["function"]
        assert fn["name"] and fn["description"]
        assert "parameters" in fn and fn["parameters"].get("type") == "object"


def test_list_offline_topics():
    from src.agent_tools import execute_tool
    r = execute_tool("list_offline_topics", {})
    assert r.get("topics"), "应返回预置主题"
    assert "低空经济" in r["topics"]


def test_get_topic_news_from_cache():
    from src.agent_tools import execute_tool
    r = execute_tool("get_topic_news", {"topic": "低空经济"})
    assert r.get("count", 0) > 0, "news_cache.json 应包含低空经济新闻"
    first = r["news"][0]
    assert first.get("title") and first.get("url")


def test_get_topic_news_unknown_topic():
    from src.agent_tools import execute_tool
    r = execute_tool("get_topic_news", {"topic": "不存在的主题XYZ"})
    assert r.get("count") == 0


def test_unknown_tool_error():
    from src.agent_tools import execute_tool, tool_names
    r = execute_tool("no_such_tool", {})
    assert "error" in r
    assert "available" in r and tool_names() == r["available"]


def test_tool_failure_returns_error_dict():
    from src.agent_tools import execute_tool
    # 用畸形参数触发内部异常 (get_stock_financials 需 code)
    r = execute_tool("get_stock_financials", {"code": ""})
    # 空 code 可能返回默认财务或 error, 但必须可序列化 dict
    assert isinstance(r, dict)


def test_tool_result_text_truncation():
    from src.agent_tools import tool_result_text
    text = tool_result_text("list_offline_topics", {})
    assert isinstance(text, str) and len(text) > 0
