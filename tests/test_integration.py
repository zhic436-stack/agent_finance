"""端到端集成测试: 输入热点 -> 事件解析 -> 产业链推理 -> 因子计算 -> 风险分析 -> 报告生成。

验证 pipeline.run_analysis 全链路协作。不依赖网络/LLM (走规则兜底路径),
保证 CI 可复现。

注意: 测试强制清空 config.ASCEND_API_KEY (即使 .env 已配置), 保证走规则兜底
路径, 避免 LLM 不确定性破坏确定性断言。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_analysis  # noqa: E402

TOPICS = ["低空经济", "AI算力", "机器人", "新能源"]


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """所有集成测试强制无 API Key (规则兜底, 确定性)。"""
    import config

    monkeypatch.setattr(config, "ASCEND_API_KEY", "")


def test_pipeline_complete_low_altitude():
    """低空经济全链路: 事件/产业链/候选股/因子/风险/报告 全部产出。"""
    result = run_analysis("低空经济", use_llm=False)

    assert result["topic"] == "低空经济"
    assert result["event"]["event_type"] in ("政策", "行业", "公司", "其他")
    assert "低空经济" in result["event"]["benefited_industries"], "应命中低空经济"
    assert len(result["chain"]) >= 3, "低空经济应推理出至少3个产业链环节"
    assert result["concepts"], "应命中东财概念"
    assert len(result["stock_results"]) > 0, "候选股不能为空"
    assert "低空经济" in result["report"], "报告应包含主题"
    assert "免责声明" in result["report"] or "不构成任何投资建议" in result["report"], "报告必须含免责声明"


def test_pipeline_all_topics():
    """4个预置热点全部可跑通。"""
    for topic in TOPICS:
        result = run_analysis(topic, use_llm=False)
        assert result["event"]["event_type"], f"{topic} 事件类型为空"
        assert len(result["stock_results"]) > 0, f"{topic} 候选股为空"
        assert result["report"], f"{topic} 报告为空"


def test_pipeline_unknown_topic_graceful():
    """未知主题: 不崩溃, 返回友好空态。"""
    result = run_analysis("一个完全不存在的主题xyz", use_llm=False)
    assert result["topic"] == "一个完全不存在的主题xyz"
    # 允许空产业链/空候选股, 但报告必须有 (模板兜底)
    assert result["report"], "未知主题报告不能为空"
    assert isinstance(result["errors"], list)


def test_pipeline_stock_schema():
    """候选股结果结构: 每只含 stock/factors/risk。"""
    result = run_analysis("机器人", use_llm=False)
    for r in result["stock_results"]:
        assert r.get("stock"), "缺 stock"
        assert r.get("factors", {}).get("composite", -1) >= 0, "缺 composite"
        assert r.get("risk", {}).get("risk_level") in ("低", "中", "高", "未知"), "缺 risk_level"


def test_pipeline_deterministic():
    """相同输入 -> 相同输出 (可复现)。"""
    r1 = run_analysis("低空经济", use_llm=False)
    r2 = run_analysis("低空经济", use_llm=False)
    assert r1["event"] == r2["event"]
    assert r1["chain"] == r2["chain"]
    # 股票结果排序后对比
    def key(x):
        return (x["stock"].code, x["factors"].get("composite", 0))
    assert sorted(r1["stock_results"], key=key) == sorted(r2["stock_results"], key=key)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
