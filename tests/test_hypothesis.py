"""研究假设生成器测试 (B1)。

验证:
1. 规则兜底: 已知主题输出完整假设结构
2. 未知主题: 不崩溃, 通用模板
3. 结构完整性: 所有字段有默认值
4. 与 pipeline 集成: run_analysis 输出含 hypothesis
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.hypothesis_generator import generate_hypothesis  # noqa: E402
from src.pipeline import run_analysis  # noqa: E402

REQUIRED_FIELDS = ["event_type", "core_logic", "propagation_path",
                   "key_companies", "verification_indicators", "uncertainties"]


def test_rule_fallback_structure():
    h = generate_hypothesis(
        {"topic": "低空经济", "event_type": "政策利好", "benefited_industries": ["低空经济"]},
        use_llm=False,
    )
    for field in REQUIRED_FIELDS:
        assert field in h, f"缺字段 {field}"
    assert h["core_logic"], "核心逻辑不能为空"
    assert h["propagation_path"], "传播路径不能为空"
    assert len(h["verification_indicators"]) >= 3, "验证指标至少3个"
    assert h["uncertainties"], "不确定性不能为空"


def test_unknown_topic_fallback():
    h = generate_hypothesis({"topic": "完全未知XYZ", "event_type": "其他"}, use_llm=False)
    assert h["core_logic"], "未知主题也应有核心逻辑"
    assert h["propagation_path"], "未知主题也应有传播路径"


def test_empty_topic():
    h = generate_hypothesis({"topic": "", "event_type": "其他"}, use_llm=False)
    assert h["core_logic"], "空主题不崩溃"


def test_pipeline_includes_hypothesis(monkeypatch):
    """run_analysis 输出含 hypothesis 字段。"""
    import config
    monkeypatch.setattr(config, "ASCEND_API_KEY", "")  # 规则兜底

    r = run_analysis("低空经济", use_llm=False, max_candidates=3, enrich_market=False)
    assert "hypothesis" in r, "pipeline 输出缺 hypothesis"
    assert r["hypothesis"].get("core_logic"), "假设核心逻辑不能为空"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
