"""Phase 2: 昇腾集成监控与解析器测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ascend_monitor import AscendMonitor  # noqa: E402
from src.llm_parser import (  # noqa: E402
    extract_json_block,
    parse_llm_response,
)

TEMPLATE = {"event_type": "其他", "industries": [], "keywords": []}


def test_extract_codeblock():
    text = '解析结果:\n```json\n{"event_type": "政策利好"}\n```'
    assert extract_json_block(text) == '{"event_type": "政策利好"}'


def test_extract_braces():
    text = '结果是 {"a": 1} 就这样'
    assert extract_json_block(text) == '{"a": 1}'


def test_parse_normal():
    r = parse_llm_response('{"event_type": "政策利好", "industries": ["低空经济"], "keywords": ["eVTOL"]}', TEMPLATE)
    assert r["event_type"] == "政策利好"
    assert r["industries"] == ["低空经济"]
    assert r["keywords"] == ["eVTOL"]


def test_parse_fullwidth():
    """全角标点也能解析。"""
    r = parse_llm_response('{"event_type": "政策利好"，"industries": ["低空经济"]}', TEMPLATE)
    assert r["event_type"] == "政策利好"


def test_parse_defaults_filled():
    """缺失字段用默认值填充。"""
    r = parse_llm_response('{"event_type": "政策利好"}', TEMPLATE)
    assert r["event_type"] == "政策利好"
    assert r["industries"] == []
    assert r["keywords"] == []


def test_parse_garbage():
    """完全非 JSON 输入 -> 默认值, 不崩溃。"""
    r = parse_llm_response("抱歉我无法理解你的请求", TEMPLATE)
    assert r == TEMPLATE


def test_parse_trailing_comma():
    """尾逗号修复。"""
    r = parse_llm_response('{"event_type": "政策利好",}', TEMPLATE)
    assert r["event_type"] == "政策利好"


def test_monitor_records():
    m = AscendMonitor()
    m.record_call(True, 3.0)
    m.record_call(False, 10.0, "Qwen")
    s = m.get_status()
    assert s["total_calls"] == 2
    assert s["success_rate"] == "50.0%"
    assert s["failed_calls"] == 1
    assert s["status"] == "degraded"


def test_monitor_healthy():
    m = AscendMonitor()
    for _ in range(10):
        m.record_call(True, 2.5)
    assert m.get_status()["status"] == "healthy"


def test_monitor_idle():
    m = AscendMonitor()
    assert m.get_status()["status"] == "idle"


def test_monitor_reset():
    m = AscendMonitor()
    m.record_call(True, 1.0)
    m.reset()
    assert m.get_status()["total_calls"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
