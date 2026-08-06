"""产业链知识图谱: 事件 -> 产业 -> 环节 -> 公司 的映射关系。

基于现有 industry_chains.json 规则库 + 离线包自动构建, 不手写重复数据。
提供图查询接口: 按事件类型/关键词搜索产业, 获取产业链各环节公司。

图谱数据源:
- 产业/环节: data/industry_chains.json (规则库)
- 环节公司: data/offline/*.json (概念成分股, 按概念映射)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 事件类型 -> 受益产业映射 (启发式, 可扩展)
_EVENT_INDUSTRY_HINTS: Dict[str, List[str]] = {
    "政策利好": ["低空经济", "新能源", "半导体", "新能源汽车", "光伏", "军工"],
    "技术突破": ["AI算力", "人工智能", "半导体", "机器人"],
    "行业景气": ["新能源", "新能源汽车", "光伏", "消费电子", "半导体"],
    "产能扩张": ["新能源汽车", "光伏", "半导体"],
    "消费升级": ["消费电子", "新能源汽车"],
}


class KnowledgeGraph:
    """知识图谱 (内存, 构建自规则库+离线包)。"""

    def __init__(self, rules_file: Path | None = None, offline_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parent.parent
        self.rules_file = rules_file or (root / "data" / "industry_chains.json")
        self.offline_dir = offline_dir or (root / "data" / "offline")
        self.graph: Dict[str, Any] = {"events": {}, "industry_chains": {}, "company_products": {}}
        self._build()

    def _build(self) -> None:
        """构建图谱: 规则库产业 + 离线包公司映射。"""
        # 1. 事件类型映射
        self.graph["events"] = dict(_EVENT_INDUSTRY_HINTS)

        # 2. 产业 -> 环节 -> 公司 (规则库 + 离线包)
        try:
            with open(self.rules_file, encoding="utf-8") as f:
                rules = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("知识图谱规则库加载失败: %s", str(e)[:60])
            rules = {}

        for topic, rule in rules.items():
            chain_info = {
                "upstream": [],
                "midstream": [],
                "downstream": [],
                "companies": {},
                "keywords": rule.get("keywords", []),
            }
            nodes = rule.get("industry_chain", [])
            # 简单按顺序: 前1/3上游, 中1/3中游, 后1/3下游
            n = len(nodes)
            for i, node in enumerate(nodes):
                name = node.get("name", "")
                if n and i < n / 3:
                    chain_info["upstream"].append(name)
                elif n and i < n * 2 / 3:
                    chain_info["midstream"].append(name)
                else:
                    chain_info["downstream"].append(name)
                # 环节 -> 公司 (离线包概念成分股)
                chain_info["companies"][name] = self._companies_for_concept(topic, node)
            self.graph["industry_chains"][topic] = chain_info

        # 3. 公司 -> 产品 (从离线包生成基础映射)
        for topic, chain_info in self.graph["industry_chains"].items():
            for companies in chain_info["companies"].values():
                for comp in companies:
                    code = comp.get("code", "")
                    if code:
                        self.graph["company_products"].setdefault(code, {
                            "name": comp.get("name", ""),
                            "products": [f"{topic}产业链相关"],
                        })

    def _companies_for_concept(self, topic: str, node: Dict[str, Any]) -> List[Dict[str, str]]:
        """从离线包取某概念成分股 (上限10只)。"""
        from src.data_collector import load_offline_stocks

        try:
            stocks = load_offline_stocks(topic)
            return [{"code": s.code, "name": s.name} for s in stocks[:10]]
        except Exception as e:  # noqa: BLE001
            logger.warning("图谱公司加载失败 %s: %s", topic, str(e)[:60])
            return []

    # ============ 查询接口 ============

    def search_by_event(self, event_type: str, keyword: str) -> List[str]:
        """根据事件类型和关键词搜索相关产业。"""
        industries = list(self.graph["events"].get(event_type, []))

        # 关键词额外匹配 (规则库关键词/环节名)
        for chain, info in self.graph["industry_chains"].items():
            if keyword in chain:
                if chain not in industries:
                    industries.append(chain)
                continue
            for kw in info.get("keywords", []):
                if kw and kw in keyword:
                    if chain not in industries:
                        industries.append(chain)
                    break
        return industries

    def get_chain_companies(self, chain: str) -> Dict[str, List[Dict[str, str]]]:
        """获取产业链各环节的公司。"""
        info = self.graph["industry_chains"].get(chain, {})
        return info.get("companies", {})

    def get_chain_transmission(self, chain: str) -> str:
        """获取产业链传导描述。"""
        info = self.graph["industry_chains"].get(chain, {})
        if not info:
            return ""
        up = "、".join(info.get("upstream", []))
        mid = "、".join(info.get("midstream", []))
        down = "、".join(info.get("downstream", []))
        return f"上游({up}) → 中游({mid}) → 下游({down})"

    def to_json(self) -> Dict[str, Any]:
        """序列化为可保存的 dict。"""
        return self.graph


# 全局单例
_graph: KnowledgeGraph | None = None


def get_kg() -> KnowledgeGraph:
    """获取全局知识图谱 (惰性构建)。"""
    global _graph
    if _graph is None:
        _graph = KnowledgeGraph()
    return _graph
