"""Phase 3: 知识图谱与产业链库测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.knowledge_graph import KnowledgeGraph  # noqa: E402

kg = KnowledgeGraph()


def test_min_industries():
    """图谱产业数 >= 5。"""
    assert len(kg.graph["industry_chains"]) >= 5


def test_each_industry_has_chain():
    """每产业至少3个环节。"""
    for chain, info in kg.graph["industry_chains"].items():
        nodes = len(info["upstream"]) + len(info["midstream"]) + len(info["downstream"])
        assert nodes >= 3, f"{chain} 环节数不足"


def test_each_chain_has_companies():
    """每环节至少1家公司。"""
    for chain, info in kg.graph["industry_chains"].items():
        for node, companies in info["companies"].items():
            assert len(companies) >= 1, f"{chain}/{node} 无公司"


def test_search_by_event():
    """事件搜索返回产业。"""
    r = kg.search_by_event("政策利好", "低空经济")
    assert "低空经济" in r


def test_get_chain_companies():
    """获取产业链环节公司。"""
    comps = kg.get_chain_companies("低空经济")
    assert "整机制造" in comps
    assert comps["整机制造"]


def test_transmission():
    """传导路径描述。"""
    t = kg.get_chain_transmission("低空经济")
    assert "→" in t


def test_company_products():
    """公司产品映射非空。"""
    assert len(kg.graph["company_products"]) > 0
    # 抽样验证
    code, info = next(iter(kg.graph["company_products"].items()))
    assert info["name"]
    assert info["products"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
