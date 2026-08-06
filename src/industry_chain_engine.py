"""产业链推演引擎: 研究假设 -> 产业链传导路径 -> 候选公司池。

三层推演:
1. 逻辑层: 从假设提取"原因->结果"传导链
2. 行业层: 映射到具体行业环节 (规则库 + 假设传播路径)
3. 公司层: 从行业环节匹配对应公司 (概念匹配 / 离线包)

兜底: 推演失败时, 直接从概念匹配获取候选池。

返回结构:
{
    "logic_chain": ["原因", "结果", ...],        # 逻辑层
    "industry_chain": ["环节1", "环节2", ...],   # 行业层
    "companies": [StockInfo, ...],               # 公司层 (候选池)
    "source": "规则推演/假设路径/概念兜底",
}
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def deduce_logic_chain(hypothesis: Dict[str, Any]) -> List[str]:
    """从假设提取因果链 (逻辑层)。

    从 core_logic ("因为A→导致B→影响C") 和 propagation_path 提取传导节点。
    """
    nodes: List[str] = []

    # 1. 从传播路径提取 (最可靠)
    for p in hypothesis.get("propagation_path", []) or []:
        node = p.get("node", "") if isinstance(p, dict) else str(p)
        if node and node not in nodes:
            nodes.append(node)

    # 2. 从 core_logic 提取箭头因果
    core = hypothesis.get("core_logic", "") or ""
    if "→" in core:
        for part in core.split("→"):
            part = part.strip().lstrip("因为").strip()
            if part and part not in nodes:
                nodes.append(part[:12])

    return nodes or ["事件驱动"]


def map_industry_layer(logic_chain: List[str], event: Dict[str, Any]) -> List[Dict[str, str]]:
    """将逻辑链映射到行业环节 (行业层)。

    优先用事件匹配产业链规则库, 其次用逻辑链关键词。
    """
    from src.event_analyzer import load_rules

    rules = load_rules()
    industries: List[Dict[str, str]] = []

    # 1. 事件受益行业匹配规则库
    for ind in event.get("benefited_industries", []) or []:
        rule = rules.get(ind)
        if rule:
            for node in rule.get("industry_chain", []):
                entry = {"industry": node.get("name", ""), "concept": ind}
                if entry not in industries:
                    industries.append(entry)

    # 2. 逻辑链关键词补充匹配
    if not industries:
        for node_name in logic_chain:
            for name, rule in rules.items():
                for kw in rule.get("keywords", []):
                    if kw and kw in node_name:
                        for node in rule.get("industry_chain", []):
                            entry = {"industry": node.get("name", ""), "concept": name}
                            if entry not in industries:
                                industries.append(entry)
                        break

    return industries


def map_company_layer(industry_chain: List[Dict[str, str]], max_companies: int = 30) -> List[Any]:
    """从行业环节匹配公司 (公司层)。用离线包概念成分股。

    兜底: 行业环节无离线包时, 尝试匹配概念名。
    """
    from src.data_collector import load_offline_stocks

    companies: List[Any] = []
    seen: set = set()
    for entry in industry_chain:
        concept = entry.get("concept", "")
        stocks = load_offline_stocks(concept)
        for s in stocks:
            if s.code not in seen:
                seen.add(s.code)
                companies.append(s)
        if len(companies) >= max_companies:
            break
    return companies[:max_companies]


def deduce_chain(hypothesis: Dict[str, Any], event: Dict[str, Any],
                 max_companies: int = 30) -> Dict[str, Any]:
    """完整产业链推演: 假设 -> 三层 -> 候选公司池。失败返回概念兜底。

    返回:
        {
            "logic_chain": [...],
            "industry_chain": [{"industry", "concept"}, ...],
            "companies": [StockInfo, ...],
            "source": "规则推演/概念兜底",
        }
    """
    result: Dict[str, Any] = {
        "logic_chain": [],
        "industry_chain": [],
        "companies": [],
        "source": "",
    }

    # 1. 逻辑层
    try:
        result["logic_chain"] = deduce_logic_chain(hypothesis)
    except Exception as e:  # noqa: BLE001
        logger.warning("逻辑层推演失败: %s", str(e)[:80])
        result["logic_chain"] = ["事件驱动"]

    # 2. 行业层
    try:
        result["industry_chain"] = map_industry_layer(result["logic_chain"], event)
    except Exception as e:  # noqa: BLE001
        logger.warning("行业层推演失败: %s", str(e)[:80])
        result["industry_chain"] = []

    # 3. 公司层
    try:
        result["companies"] = map_company_layer(result["industry_chain"], max_companies)
        result["source"] = "规则推演" if result["industry_chain"] else "概念兜底"
    except Exception as e:  # noqa: BLE001
        logger.warning("公司层推演失败: %s", str(e)[:80])

    # 兜底: 行业层失败时直接用概念匹配
    if not result["companies"]:
        try:
            from src.data_collector import load_offline_stocks
            for ind in event.get("benefited_industries", []) or []:
                stocks = load_offline_stocks(ind)
                result["companies"].extend(stocks)
                if len(result["companies"]) >= max_companies:
                    break
            result["source"] = "概念兜底"
        except Exception as e:  # noqa: BLE001
            logger.warning("概念兜底失败: %s", str(e)[:80])

    # 去重
    seen: set = set()
    result["companies"] = [c for c in result["companies"] if not (c.code in seen or seen.add(c.code))][:max_companies]
    return result
