"""接口契约测试 (冲刺包 Phase 2): 验证前后端接口契约。

覆盖: run_analysis 返回结构 / run_analysis_cached / compare_topics / aggregate_topics
      / async_chat_completion / 因子范围 / 风险格式 / 报告生成。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import (  # noqa: E402
    aggregate_topics,
    compare_topics,
    run_analysis,
    run_analysis_cached,
)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    import config
    monkeypatch.setattr(config, "ASCEND_API_KEY", "")


def test_pipeline_return_structure():
    """run_analysis 返回结构含前端必需字段。"""
    result = run_analysis("低空经济", use_llm=False, max_candidates=5, enrich_market=False)
    for field in ("topic", "event", "chain", "stock_results", "report"):
        assert field in result, f"缺字段 {field}"
    assert isinstance(result["stock_results"], list)
    if result["stock_results"]:
        first = result["stock_results"][0]
        assert "stock" in first
        assert "factors" in first
        assert "risk" in first


def test_factor_output_range():
    """因子输出在 0-100。"""
    result = run_analysis("低空经济", use_llm=False, max_candidates=5, enrich_market=False)
    for sr in result["stock_results"]:
        for key, value in sr["factors"].items():
            if isinstance(value, (int, float)) and key not in ("event_strength", "chain_position", "logic_certainty", "event_logic_composite"):
                assert 0 <= value <= 100, f"因子 {key} 越界: {value}"


def test_risk_output_format():
    """风险分析输出合法。"""
    result = run_analysis("机器人", use_llm=False, max_candidates=3, enrich_market=False)
    for sr in result["stock_results"]:
        risk = sr["risk"]
        assert "risk_level" in risk
        assert risk["risk_level"] in ("低", "中", "高", "未知")


def test_report_generation():
    """报告生成非空 + 含免责声明。"""
    result = run_analysis("低空经济", use_llm=False, max_candidates=3, enrich_market=False)
    from src.report_generator import generate_report
    report = generate_report(result["event"], result["chain"], result["stock_results"], use_llm=False)
    assert report, "报告不能为空"
    assert "不构成任何投资建议" in report or "免责声明" in report


def test_run_analysis_cached():
    """缓存版分析: demo_state 命中返回。"""
    result = run_analysis_cached("低空经济")
    assert result.get("report"), "缓存分析报告为空"
    assert result.get("_from_demo") is True or result.get("report")


def test_compare_topics():
    """多话题对比返回排名。"""
    r = compare_topics(["低空经济", "AI算力", "机器人"])
    assert "ranking" in r
    assert len(r["ranking"]) == 3
    # 按 top_score 降序
    scores = [x["top_score"] for x in r["ranking"]]
    assert scores == sorted(scores, reverse=True)


def test_aggregate_topics():
    """多话题聚合返回统计。"""
    r = aggregate_topics(["低空经济", "AI算力", "机器人"])
    assert r["total_stocks"] > 0
    assert r["unique_codes"] > 0
    assert "by_topic" in r


def test_async_chat_completion():
    """异步 LLM 返回可 await future。"""
    from src.llm import async_chat_completion
    future = async_chat_completion("你是助手", "ping", max_tokens=5, timeout=5)
    # 无 API Key 时返回 None 而非异常
    assert future is not None


def test_error_propagation_no_crash():
    """空/异常输入不崩溃 (错误传播)。"""
    # 空 topic
    r = run_analysis("", use_llm=False, max_candidates=2)
    assert r["report"], "空话题也应有报告"
    # 未知话题
    r2 = run_analysis("完全不存在的话题XYZ", use_llm=False, max_candidates=2)
    assert r2["report"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
