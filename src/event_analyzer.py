"""事件分析器: 事件理解 + 产业链推理 + 概念映射。

设计要点:
- parse_event 调用昇腾云 LLM (失败走规则兜底)
- deduce_industry_chain 纯规则: 基于 industry_chains.json 关键词匹配
- find_matching_concepts 将产业链环节映射到东财概念名 (含别名映射)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from config import CONCEPT_ALIAS, RULES_FILE

logger = logging.getLogger(__name__)

# ============ 规则库加载 ============

_RULES_CACHE: Dict[str, Any] = {}


def load_rules() -> Dict[str, Any]:
    """加载产业链规则库。失败返回空 dict。"""
    global _RULES_CACHE
    if _RULES_CACHE:
        return _RULES_CACHE
    try:
        with open(RULES_FILE, encoding="utf-8") as f:
            _RULES_CACHE = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("规则库加载失败: %s", str(e)[:100])
        _RULES_CACHE = {}
    return _RULES_CACHE


# ============ 事件解析 ============


def parse_event(topic: str) -> Dict[str, Any]:
    """LLM 解析事件: 事件类型(政策/行业/公司)、受益行业、关键词。

    失败或 LLM 不可用 -> 规则兜底: 按关键词匹配规则库已知主题。
    返回结构:
    {
        "topic": 原始输入,
        "event_type": "政策/行业/公司/其他",
        "benefited_industries": [...],
        "keywords": [...]
    }
    """
    topic = (topic or "").strip()
    if not topic:
        return {"topic": "", "event_type": "其他", "benefited_industries": [], "keywords": []}

    # 1. 尝试 LLM
    try:
        from src.llm import chat_json

        system = (
            "你是金融事件分析助手。给定一个热点主题, 输出JSON: "
            '{"event_type": "政策/行业/公司/其他", '
            '"benefited_industries": ["受益行业名", ...], '
            '"keywords": ["主题关键词", ...]}。只输出JSON。'
        )
        result = chat_json(system, topic, temperature=0.1, max_tokens=300,
                           model="event", retries=0, timeout=20)
        if result and result.get("event_type"):
            result.setdefault("topic", topic)
            result.setdefault("benefited_industries", [])
            result.setdefault("keywords", [])
            return result
    except Exception as e:  # noqa: BLE001
        logger.warning("parse_event LLM 失败, 走规则兜底: %s", str(e)[:100])

    # 2. 规则兜底: 匹配已知主题
    rules = load_rules()
    matched_industries: List[str] = []
    keywords: List[str] = []
    for name, rule in rules.items():
        for kw in rule.get("keywords", []):
            if kw and kw in topic:
                if name not in matched_industries:
                    matched_industries.append(name)
                keywords.append(kw)
                break

    return {
        "topic": topic,
        "event_type": "政策" if topic and re.search(r"政策|规划|意见|通知|方案|纲要", topic) else "行业",
        "benefited_industries": matched_industries,
        "keywords": keywords,
    }


# ============ 产业链推理 ============


def deduce_industry_chain(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """基于规则库和主题别名推理产业链传导路径。"""
    rules = load_rules()
    candidates = list(event.get("benefited_industries") or event.get("beneficiary_sectors") or [])
    if event.get("topic"):
        candidates.append(event["topic"])
    candidates.extend(event.get("keywords") or [])

    matched_concepts: List[str] = []
    for candidate in candidates:
        candidate_text = str(candidate).strip()
        if not candidate_text:
            continue
        concept = candidate_text if candidate_text in rules else next(
            (
                name
                for name, rule in rules.items()
                if any(
                    keyword and (keyword in candidate_text or candidate_text in keyword)
                    for keyword in [name, *rule.get("keywords", [])]
                )
            ),
            None,
        )
        if concept and concept not in matched_concepts:
            matched_concepts.append(concept)

    chains: List[Dict[str, Any]] = []
    seen_nodes = set()
    for concept in matched_concepts:
        rule = rules[concept]
        for node in rule.get("industry_chain", []):
            node_name = node.get("name", "")
            node_key = (concept, node_name)
            if node_key in seen_nodes:
                continue
            seen_nodes.add(node_key)
            chains.append({
                "name": node_name,
                "keywords": node.get("keywords", []),
                "companies": [],
                "concept": concept,
                "transmission": rule.get("transmission", ""),
            })
    return chains


# ============ 概念映射 ============

def find_matching_concepts(chain: List[Dict[str, Any]]) -> List[str]:
    """将产业链环节映射到东财概念名 (含别名映射)。

    逻辑:
    1. 先用环节名直接匹配东财概念 (经 CONCEPT_ALIAS 反查)
    2. 不中则用环节关键词模糊匹配
    返回东财概念名列表 (用于 get_concept_stocks)。
    """
    if not chain:
        return []

    from src.data_collector import get_concept_list

    concepts = get_concept_list()
    name_to_code = {c["name"]: c["code"] for c in concepts}
    # 别名反查: 标准名 -> 东财名
    alias_reverse = {v: k for k, v in CONCEPT_ALIAS.items()}

    matched: List[str] = []
    for node in chain:
        node_name = node.get("name", "")
        # 环节名可能不是概念名, 但所属主题 "concept" 是标准名 -> 先映射到东财名
        topic = node.get("concept", "")
        em_topic = CONCEPT_ALIAS.get(topic, topic)
        if em_topic in name_to_code and em_topic not in matched:
            matched.append(em_topic)

        # 环节关键词尝试匹配概念名
        for kw in node.get("keywords", []):
            for cname in name_to_code:
                if kw and kw in cname and cname not in matched:
                    matched.append(cname)
    return matched
