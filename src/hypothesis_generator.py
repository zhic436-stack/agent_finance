"""研究假设生成器: 输入事件 -> 输出研究假设。

研究假设是"可验证的因果推断": 从事件出发, 推出传导路径、关键公司、
验证指标与不确定性。这是"假设 -> 验证"研究范式的核心。

双路径:
- LLM 路径: 调用昇腾云生成完整假设 (需 ASCEND_API_KEY)
- 规则兜底: 用产业链规则库 + 已知主题模板组装 (确定性, 离线可用)

返回结构 (与 UI/pipeline 约定):
{
    "event_type": "政策利好/行业景气/...",
    "core_logic": "核心因果逻辑一句话",
    "propagation_path": [{"node": "环节名", "description": "说明"}, ...],
    "key_companies": ["000099", ...],
    "verification_indicators": ["新闻数量", "概念匹配度", "估值水平", "市场关注度"],
    "uncertainties": ["不确定性1", ...],
}
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 规则兜底: 已知主题 -> 传播路径模板
_RULE_PATHS: Dict[str, List[Dict[str, str]]] = {
    "低空经济": [
        {"node": "政策发布", "description": "国家层面出台低空经济指导意见, 开放低空空域"},
        {"node": "直接受益", "description": "通航运营商获得更多飞行许可, 运营收入提升"},
        {"node": "间接受益", "description": "eVTOL/无人机整机制造商获得订单预期"},
        {"node": "衍生受益", "description": "空管系统、起降场等基础设施需求增加"},
    ],
    "AI算力": [
        {"node": "需求爆发", "description": "大模型训练与推理需求推动算力建设"},
        {"node": "直接受益", "description": "AI芯片、服务器制造商订单增长"},
        {"node": "间接受益", "description": "算力租赁、数据中心运营商业绩改善"},
        {"node": "衍生受益", "description": "光模块、液冷等配套环节需求释放"},
    ],
    "机器人": [
        {"node": "产业政策", "description": "人形机器人产业政策与地方配套支持"},
        {"node": "直接受益", "description": "核心零部件(减速器/伺服)厂商订单增长"},
        {"node": "间接受益", "description": "传感器、机器视觉配套需求增加"},
        {"node": "衍生受益", "description": "本体制造、系统集成环节放量"},
    ],
    "新能源": [
        {"node": "双碳政策", "description": "双碳目标推动新能源装机持续增长"},
        {"node": "直接受益", "description": "上游材料(硅料/锂矿)需求提升"},
        {"node": "间接受益", "description": "中游电池/组件制造放量"},
        {"node": "衍生受益", "description": "下游储能、充电基础设施渗透率提升"},
    ],
}

_VERIFICATION_INDICATORS = ["新闻数量", "概念匹配度", "估值水平", "市场关注度"]
_DEFAULT_UNCERTAINTIES = [
    "政策落地时间不确定",
    "行业竞争格局可能变化",
    "需求增速可能不及预期",
]


def _rule_fallback(topic: str, event_type: str) -> Dict[str, Any]:
    """规则兜底: 从产业链规则库生成研究假设。"""
    from src.event_analyzer import load_rules

    rules = load_rules()
    hypothesis: Dict[str, Any] = {
        "event_type": event_type,
        "core_logic": "",
        "propagation_path": [],
        "key_companies": [],
        "verification_indicators": list(_VERIFICATION_INDICATORS),
        "uncertainties": list(_DEFAULT_UNCERTAINTIES),
    }

    # 匹配已知主题
    for name, rule in rules.items():
        if name in topic:
            hypothesis["core_logic"] = rule.get("transmission", "")
            # 从产业链环节构建传播路径
            for node in rule.get("industry_chain", []):
                hypothesis["propagation_path"].append({
                    "node": node.get("name", ""),
                    "description": "产业链" + node.get("name", "") + "环节",
                })
            break

    if not hypothesis["core_logic"]:
        # 未匹配: 用通用模板
        hypothesis["core_logic"] = f"市场对{event_type}事件的关注度提升, 相关受益方向值得跟踪"
        hypothesis["propagation_path"] = [
            {"node": "事件催化", "description": f"{topic} 相关事件引发市场关注"},
            {"node": "概念发酵", "description": "相关概念板块获得资金关注"},
        ]
    return hypothesis


def generate_hypothesis(event: Dict[str, Any], use_llm: bool = True) -> Dict[str, Any]:
    """生成研究假设 (LLM 优先, 规则兜底)。失败返回规则兜底, 不抛异常。

    参数:
        event: parse_event 输出 {topic, event_type, benefited_industries, keywords}
        use_llm: 是否尝试 LLM 生成
    """
    topic = event.get("topic", "")
    event_type = event.get("event_type", "其他")
    if not topic:
        return _rule_fallback("", event_type)

    # 1. LLM 路径 (B4: 产业链推理用轻量模型)
    if use_llm:
        try:
            from src.llm import chat_json

            system = (
                "你是金融研究助手。基于给定事件生成研究假设, 输出JSON: "
                '{"event_type": "政策利好/行业景气/公司事件/其他", '
                '"core_logic": "核心因果逻辑(因为A→导致B→影响C)", '
                '"propagation_path": [{"node": "环节名", "description": "说明"}], '
                '"key_companies": ["股票代码"], '
                '"verification_indicators": ["验证指标"], '
                '"uncertainties": ["不确定性"]}. 只输出JSON。'
            )
            user = (
                f"事件: {topic} (类型: {event_type}, 受益行业: "
                f"{'、'.join(event.get('benefited_industries', []))})"
            )
            result = chat_json(system, user, temperature=0.3, max_tokens=600,
                               model="chain")
            if result and result.get("core_logic"):
                result.setdefault("verification_indicators", list(_VERIFICATION_INDICATORS))
                result.setdefault("uncertainties", list(_DEFAULT_UNCERTAINTIES))
                result.setdefault("propagation_path", [])
                result.setdefault("key_companies", [])
                return result
        except Exception as e:  # noqa: BLE001 - LLM 失败走规则兜底
            logger.warning("研究假设 LLM 生成失败, 走规则兜底: %s", str(e)[:100])

    # 2. 规则兜底
    return _rule_fallback(topic, event_type)
