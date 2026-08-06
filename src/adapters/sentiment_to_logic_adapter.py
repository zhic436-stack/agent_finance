"""舆情→逻辑链适配器 (终轮 P4, DeepEar 等效方案)。

DeepEar (HKUST) 实为音频事件检测模型, 非金融舆情工具 (上轮已核实)。
按任务候选3方案: 用 LLM + 规则构建"舆情文本 → 逻辑链"模块。

功能:
  输入: 舆情文本 (新闻标题/热点)
  输出: 逻辑链 {event, impact, beneficiaries, chain, confidence}

双路径:
  - LLM: 调用昇腾云生成结构化逻辑链
  - 规则兜底: 事件类型 -> 影响方向 -> 受益行业映射 (离线可用)

验证: python -c "from src.adapters.sentiment_to_logic_adapter import sentiment_to_logic_chain; ..."
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 规则兜底: 事件关键词 -> (影响方向, 受益行业, 逻辑链)
_RULE_IMPLICATIONS: List[Dict[str, Any]] = [
    {
        "keywords": ["政策", "发布", "规划", "支持"],
        "impact": "政策红利释放, 行业预期改善",
        "beneficiaries": ["低空经济", "新能源", "半导体"],
        "chain": "政策发布 → 行业预期改善 → 需求增长 → 相关企业受益",
    },
    {
        "keywords": ["技术", "突破", "研发", "发布新"],
        "impact": "技术产业化加速, 成本下降",
        "beneficiaries": ["AI算力", "人工智能", "机器人"],
        "chain": "技术突破 → 产业化加速 → 成本下降 → 应用普及",
    },
    {
        "keywords": ["涨价", "供不应求", "紧缺"],
        "impact": "供需紧张, 产品涨价周期",
        "beneficiaries": ["半导体", "光伏", "新能源"],
        "chain": "供给紧张 → 产品涨价 → 毛利率提升 → 业绩兑现",
    },
    {
        "keywords": ["销量", "渗透率", "增长"],
        "impact": "需求景气, 行业放量",
        "beneficiaries": ["新能源汽车", "消费电子"],
        "chain": "需求增长 → 渗透率提升 → 产能扩张 → 营收增长",
    },
    {
        "keywords": ["风险", "处罚", "违规", "立案"],
        "impact": "合规风险暴露, 短期承压",
        "beneficiaries": [],
        "chain": "负面事件 → 市场担忧 → 股价承压 → 估值下修",
    },
]
_DEFAULT_CHAIN = "事件催化 → 市场关注 → 资金流入 → 相关板块活跃"


def _rule_match(text: str) -> Dict[str, Any]:
    """规则兜底: 关键词匹配生成逻辑链。"""
    for rule in _RULE_IMPLICATIONS:
        if any(kw in text for kw in rule["keywords"]):
            return {
                "event": text,
                "impact": rule["impact"],
                "beneficiaries": rule["beneficiaries"],
                "chain": rule["chain"],
                "confidence": 0.6,
                "source": "rule",
            }
    return {
        "event": text,
        "impact": "市场关注度提升, 相关方向值得跟踪",
        "beneficiaries": [],
        "chain": _DEFAULT_CHAIN,
        "confidence": 0.4,
        "source": "rule_fallback",
    }


def sentiment_to_logic_chain(text: str, use_llm: bool = True) -> Dict[str, Any]:
    """舆情文本 → 逻辑链。失败走规则兜底, 不抛异常。

    参数:
        text: 舆情文本 (新闻标题/热点关键词)
        use_llm: 是否尝试 LLM 生成

    返回: {event, impact, beneficiaries, chain, confidence, source}
    """
    text = (text or "").strip()
    if not text:
        return _rule_match("")

    # 1. LLM 路径
    if use_llm:
        try:
            from src.llm import chat_json

            system = (
                "你是金融舆情分析助手。将舆情文本转为逻辑链, 输出JSON: "
                '{"impact": "影响描述", '
                '"beneficiaries": ["受益行业/公司"], '
                '"chain": "因果链(事件→影响→受益)", '
                '"confidence": 0.0-1.0}. 只输出JSON。'
            )
            result = chat_json(system, text, temperature=0.2, max_tokens=300,
                               model="event", retries=0, timeout=25)
            if result and result.get("chain"):
                result.setdefault("event", text)
                result.setdefault("impact", result.get("chain", "")[:50])
                result.setdefault("beneficiaries", [])
                result.setdefault("confidence", 0.7)
                result["source"] = "llm"
                return result
        except Exception as e:  # noqa: BLE001
            logger.warning("舆情逻辑链 LLM 失败, 走规则: %s", str(e)[:80])

    # 2. 规则兜底
    return _rule_match(text)


def logic_chain_to_hypothesis(logic: Dict[str, Any]) -> Dict[str, Any]:
    """逻辑链 → 研究假设 (接入 pipeline.hypothesis)。"""
    chain = logic.get("chain", "")
    nodes = [n.strip() for n in chain.split("→") if n.strip()]
    return {
        "event_type": "行业景气" if logic.get("confidence", 0) > 0.5 else "其他",
        "core_logic": chain,
        "propagation_path": [{"node": n, "description": "传导环节"} for n in nodes],
        "key_companies": logic.get("beneficiaries", []),
        "verification_indicators": ["新闻数量", "概念匹配度", "估值水平"],
        "uncertainties": ["政策落地节奏", "行业竞争格局"],
    }


if __name__ == "__main__":
    r = sentiment_to_logic_chain("低空经济政策发布, 空域管理放开")
    print("OK")
    print(f"事件: {r['event']}")
    print(f"影响: {r['impact']}")
    print(f"受益方: {r['beneficiaries']}")
    print(f"逻辑链: {r['chain']}")
    print(f"置信度: {r['confidence']} | 来源: {r['source']}")
