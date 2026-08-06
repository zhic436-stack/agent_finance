"""报告生成器: 整合事件/产业链/因子/风险, 生成 Markdown 研究报告。

双路径:
- LLM 路径: 调用昇腾云 GLM-5.2 生成完整报告 (需 .env 配置 ASCEND_API_KEY)
- 规则兜底: LLM 不可用时, 用模板拼接结构化内容, 保证页面永不出错

设计要点:
- 所有 section 数据来自上游模块, 本模块只做组装与润色
- 免责声明强制追加, 不可被 LLM 覆盖
- 失败逐级降级: LLM 失败 -> 模板; 模板拼接字段缺失 -> 填空
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 事件类型 -> 中文说明
_EVENT_TYPE_CN = {
    "政策": "政策驱动",
    "行业": "行业景气",
    "公司": "公司基本面",
    "其他": "多因素",
}


def generate_report(
    event: Dict[str, Any],
    chain: List[Dict[str, Any]],
    stock_results: List[Dict[str, Any]],
    use_llm: bool = True,
) -> str:
    """生成研究报告 (Markdown)。

    参数:
        event: parse_event 输出 {topic, event_type, benefited_industries, keywords}
        chain: deduce_industry_chain 输出 [{name, keywords, concept, transmission}]
        stock_results: [{stock, factors, risk}] 因子与风险已算好的股票列表
        use_llm: 是否尝试 LLM 润色 (默认 True, 失败自动降级模板)

    返回: 完整 Markdown 报告, 始终包含免责声明。
    """
    # 1. 先构建结构化数据 (无论走哪条路径都需要)
    sections = _build_sections(event, chain, stock_results)

    # 2. 尝试 LLM 润色 (可选)
    if use_llm:
        try:
            from src.llm import chat_completion
            from config import ASCEND_API_KEY

            if ASCEND_API_KEY:
                prompt = _build_llm_prompt(event, chain, stock_results)
                content = chat_completion(
                    system="你是专业金融研究员, 生成简洁的研究报告正文, 用中文, 不要编造数据, 不要包含免责声明。",
                    user=prompt,
                    temperature=0.4,
                    max_tokens=1200,
                    timeout=90,  # 长文本报告生成需更长超时 (实测 300-500字需 30s+)
                )
                if content:
                    return _finalize_report(content, sections)
        except Exception as e:  # noqa: BLE001 - LLM 失败走模板
            logger.warning("LLM 报告生成失败, 降级模板: %s", str(e)[:100])

    # 3. 规则模板兜底
    body = _render_template(sections)
    return _finalize_report(body, sections)


def _finalize_report(body: str, sections: Dict[str, Any]) -> str:
    """追加元信息与免责声明。"""
    meta = sections["meta"]
    footer = (
        "\n\n---\n"
        f"*数据来源: {meta['source']} | 生成时间: {meta['timestamp']}*\n\n"
        "> **免责声明**: 本报告由 AI 系统自动生成, 仅作研究参考, "
        "不构成任何投资建议。投资有风险, 入市需谨慎。"
    )
    return body + footer


def _build_sections(
    event: Dict[str, Any],
    chain: List[Dict[str, Any]],
    stock_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """组装报告各部分结构化数据 (LLM 与模板共用)。"""
    from datetime import datetime

    topic = event.get("topic", "")
    event_type = _EVENT_TYPE_CN.get(event.get("event_type", ""), event.get("event_type", "其他"))
    industries = event.get("benefited_industries", []) or []
    keywords = event.get("keywords", []) or []

    chain_nodes = [n.get("name", "") for n in chain]
    transmission = chain[0].get("transmission", "") if chain else ""

    # 股票排序: 按综合分降序
    ranked = sorted(stock_results, key=lambda r: r.get("factors", {}).get("composite", 0), reverse=True)
    top5 = ranked[:5]

    return {
        "meta": {
            "source": "东方财富(akshare) / 离线缓存包",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "event": {
            "topic": topic,
            "event_type": event_type,
            "industries": industries,
            "keywords": keywords,
        },
        "chain": {
            "nodes": chain_nodes,
            "transmission": transmission,
        },
        "stocks": [
            {
                "code": r.get("stock").code if r.get("stock") else "",
                "name": r.get("stock").name if r.get("stock") else "",
                "factors": r.get("factors", {}),
                "risk": r.get("risk", {}),
            }
            for r in ranked
        ],
        "top5": top5,
    }


def _build_llm_prompt(event: Dict[str, Any], chain: List[Dict[str, Any]], stock_results: List[Dict[str, Any]]) -> str:
    """构造 LLM 提示词, 附上结构化事实, 防止编造。

    输入: 事件摘要 + 产业链 + 因子 Top5 + 风险
    输出: 专业研究报告风格 Markdown, 约束不输出投资建议。
    """
    lines: List[str] = []
    lines.append("请基于以下事实撰写一份专业金融研究报告(Markdown), 包含: 事件摘要、影响链分析、个股点评。")
    lines.append("要求: 语言专业客观, 基于给定事实, 不编造数据, 不输出投资建议, 不推荐买卖。\n")

    # 1. 事件摘要
    lines.append("【事件摘要】")
    lines.append(f"- 研究主题: {event.get('topic', '')}")
    lines.append(f"- 事件类型: {event.get('event_type', '')}")
    lines.append(f"- 受益行业: {', '.join(event.get('benefited_industries', [])) or '未识别'}")
    lines.append(f"- 关键词: {', '.join(event.get('keywords', [])) or '无'}\n")

    # 2. 产业链
    lines.append("【影响链】")
    if chain:
        lines.append(f"- 传导路径: {chain[0].get('transmission', '')}")
        lines.append(f"- 产业链环节: {' → '.join(n.get('name', '') for n in chain)}")
    else:
        lines.append("- 未匹配到产业链规则")
    lines.append("")

    # 3. 因子 Top5
    lines.append("【多因子评分 Top5】(综合分=事件30%+价值25%+成长25%+市场20%)")
    ranked = sorted(stock_results, key=lambda x: x.get('factors', {}).get('composite', 0), reverse=True)[:5]
    for i, r in enumerate(ranked, 1):
        s = r.get("stock")
        f = r.get("factors", {})
        k = r.get("risk", {})
        if s:
            lines.append(
                f"{i}. {s.name}({s.code}): 综合{f.get('composite', 0)}, "
                f"事件{f.get('event', 0)}/价值{f.get('value', 0)}/成长{f.get('growth', 0)}/市场{f.get('market', 0)}, "
                f"风险等级{k.get('risk_level', '未知')}"
            )
    lines.append("")
    lines.append("请输出报告正文(300-500字), 用中文, 每个股票点评控制在2-3句。")
    return "\n".join(lines)


def _render_template(sections: Dict[str, Any]) -> str:
    """规则模板渲染报告正文。"""
    ev = sections["event"]
    ch = sections["chain"]
    lines: List[str] = []

    lines.append(f"# {ev['topic']} 研究报告\n")
    lines.append(f"**事件类型**: {ev['event_type']}")
    lines.append(f"**受益行业**: {'、'.join(ev['industries']) if ev['industries'] else '未识别'}")
    lines.append(f"**关键词**: {'、'.join(ev['keywords']) if ev['keywords'] else '无'}\n")

    lines.append("## 一、影响链分析\n")
    if ch["transmission"]:
        lines.append(f"> {ch['transmission']}\n")
    if ch["nodes"]:
        lines.append("产业链环节: " + " → ".join(ch["nodes"]) + "\n")
    else:
        lines.append("未匹配到产业链规则。\n")

    lines.append("## 二、个股多因子排名\n")
    stocks = sections["stocks"]
    if stocks:
        lines.append("| 排名 | 代码 | 名称 | 综合分 | 事件 | 价值 | 成长 | 市场 | 风险 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for i, s in enumerate(stocks[:5], 1):
            f = s["factors"]
            r = s["risk"]
            lines.append(
                f"| {i} | {s['code']} | {s['name']} | {f.get('composite', 0):.1f} "
                f"| {f.get('event', 0):.1f} | {f.get('value', 0):.1f} "
                f"| {f.get('growth', 0):.1f} | {f.get('market', 0):.1f} "
                f"| {r.get('risk_level', '未知')} |"
            )
    else:
        lines.append("无有效股票数据。\n")

    lines.append("\n## 三、风险提示\n")
    high_risk = [s for s in stocks if s.get("risk", {}).get("risk_level") == "高"]
    if high_risk:
        names = "、".join(s["name"] for s in high_risk)
        lines.append(f"- ️ 高风险标的: {names}, 建议重点关注风险控制")
    else:
        lines.append("- 当前标的整体风险可控")

    return "\n".join(lines)
