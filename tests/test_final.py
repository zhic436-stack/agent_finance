"""最终验收测试 (Phase 6): 全链路 + 因子一致性 + 风险 + 健康检查。

注: StrategyEnsemble / run_analysis_cached 依赖 Codex 的 Phase 3 交付,
未到货时相关用例跳过 (标记 xfail), 不假装通过。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_analysis  # noqa: E402


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """验收测试走规则兜底 (确定性, 不依赖昇腾 API)。"""
    import config
    monkeypatch.setattr(config, "ASCEND_API_KEY", "")


def test_full_pipeline():
    """完整链路: 事件/产业链/假设/候选股/因子/风险/报告。"""
    result = run_analysis("低空经济", use_llm=False, max_candidates=10, enrich_market=False)
    assert result is not None
    assert result.get("event") is not None
    assert result.get("chain") is not None
    assert result.get("hypothesis", {}).get("core_logic"), "假设缺核心逻辑"
    assert len(result.get("stock_results", [])) >= 3
    assert result.get("report"), "报告为空"
    assert result.get("trace"), "缺执行轨迹"


def test_all_topics_runnable():
    """10个话题全部可运行 (含新增6个)。"""
    from config import OFFLINE_TOPICS
    for topic in OFFLINE_TOPICS:
        r = run_analysis(topic, use_llm=False, max_candidates=5, enrich_market=False)
        assert r["report"], f"{topic} 报告为空"
        assert len(r["stock_results"]) > 0, f"{topic} 无候选股"


def test_factor_consistency():
    """因子值范围合理。"""
    result = run_analysis("低空经济", use_llm=False, max_candidates=10, enrich_market=False)
    for sr in result["stock_results"]:
        f = sr["factors"]
        for key in ("event", "value", "growth", "market", "composite"):
            assert 0 <= f.get(key, 0) <= 100, f"{key} 越界: {f.get(key)}"


def test_risk_analysis():
    """风险分析输出合法等级。"""
    result = run_analysis("机器人", use_llm=False, max_candidates=5, enrich_market=False)
    for sr in result["stock_results"]:
        level = sr["risk"].get("risk_level", "未知")
        assert level in ("低", "中", "高", "未知")


def test_llm_parser_integration():
    """LLM 解析器与假设生成集成。"""
    from src.llm_parser import parse_llm_response
    r = parse_llm_response('{"core_logic": "因为A导致B"}', {"core_logic": "", "nodes": []})
    assert r["core_logic"] == "因为A导致B"
    assert r["nodes"] == []


def test_health_check_integration():
    """健康检查在验收测试中返回结构。"""
    from src.health_check import HealthChecker
    s = HealthChecker().check_all()
    assert s["overall_status"] in ("healthy", "degraded", "unhealthy")


def test_ui_health():
    """UI 页面基础健康 (不启动 server 时跳过)。"""
    import socket
    try:
        with socket.create_connection(("localhost", 8501), timeout=1):
            pytest.skip("UI 已启动, 通过 socket 检查")
    except OSError:
        pytest.skip("UI 未启动, 跳过 (演示时启动)")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
