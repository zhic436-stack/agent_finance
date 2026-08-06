# -*- coding: utf-8 -*-
"""金融研究 Agent 工具层: 把现有数据/分析函数封装为 LLM 可调用工具 (OpenAI schema)。

每个工具都是"原子"操作, 由 ReAct 编排器 (src/orchestrator.py) 让模型自主选择调用。
结果统一为可 JSON 序列化的 dict, 并做截断防上下文膨胀。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============ 工具 schema (OpenAI function calling 格式) ============

_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "parse_event",
            "description": "解析金融热点主题, 识别事件类型(政策/行业/公司/其他)、受益行业、关键词。研究任何主题的第一步。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "热点主题, 如 '低空经济政策'"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deduce_industry_chain",
            "description": "根据事件解析结果推导产业链受益环节(上中下游)。需要先调用 parse_event。",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_json": {"type": "string", "description": "parse_event 返回的 JSON 字符串"},
                },
                "required": ["event_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_matching_concepts",
            "description": "把产业链环节映射到可交易的东财概念板块。需要先调用 deduce_industry_chain。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain_json": {"type": "string", "description": "deduce_industry_chain 返回的 JSON 字符串"},
                },
                "required": ["chain_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_concept_stocks",
            "description": "获取某概念板块的成分股列表(代码/名称/现价/当日涨跌幅), 用于确定候选股票池。",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string", "description": "概念板块名, 如 '低空经济'、'算力概念'"},
                },
                "required": ["concept"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_market_data",
            "description": "获取个股近 N 日行情(收盘价序列/涨跌幅/波动率/最大回撤), 用于市场因子与技术面分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "6 位股票代码, 如 '920961'"},
                    "days": {"type": "integer", "description": "最近交易日数, 默认 20", "minimum": 5, "maximum": 60},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_financials",
            "description": "获取个股财务指标(PE/PB/ROE/成长), 用于价值与成长因子分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "6 位股票代码, 如 '920961'"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_news",
            "description": "获取个股近期新闻标题与摘要, 用于事件因子与舆情判断。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "6 位股票代码, 如 '920961'"},
                    "days": {"type": "integer", "description": "回溯天数, 默认 3", "minimum": 1, "maximum": 10},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_risk",
            "description": "评估个股风险等级(低/中/高/数据暂缺)、年化波动率、最大回撤、估值风险。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "6 位股票代码, 如 '920961'"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_topic_news",
            "description": "获取某研究主题的最新政策/行业新闻 (来自联网搜索缓存, 时效性强, 适合补充事件与舆情判断)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "研究主题, 如 '低空经济'、'AI算力'"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_offline_topics",
            "description": "列出系统内置的离线研究主题(成分股已预置), 用于快速定位可研究的主题。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def get_tool_schemas() -> List[Dict[str, Any]]:
    """返回工具 schema 列表 (供 LLM tools 参数)。"""
    return list(_TOOLS)


def tool_names() -> List[str]:
    return [t["function"]["name"] for t in _TOOLS]


# ============ 结果截断 (防上下文膨胀) ============

def _truncate_text(text: str, limit: int = 400) -> str:
    text = text or ""
    return text[:limit] + ("…" if len(text) > limit else "")


def _safe_json(obj: Any, limit: int = 3000) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(obj)
    return s[:limit] + ("…" if len(s) > limit else "")


# ============ 工具执行 ============

def _exec_parse_event(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.event_analyzer import parse_event
    return parse_event(str(args.get("topic", "")).strip())


def _exec_deduce_chain(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.event_analyzer import deduce_industry_chain
    event = json.loads(args.get("event_json", "{}")) if isinstance(args.get("event_json"), str) else args.get("event_json") or {}
    if not isinstance(event, dict):
        event = {}
    return {"chain": deduce_industry_chain(event)}


def _exec_find_concepts(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.event_analyzer import find_matching_concepts
    chain = json.loads(args.get("chain_json", "[]")) if isinstance(args.get("chain_json"), str) else args.get("chain_json") or []
    if not isinstance(chain, list):
        chain = []
    return {"concepts": find_matching_concepts(chain)}


def _exec_concept_stocks(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.data_collector import get_concept_stocks
    stocks = get_concept_stocks(str(args.get("concept", "")).strip())
    return {"stocks": [
        {"code": s.code, "name": s.name, "price": getattr(s, "price", 0), "pct_chg": getattr(s, "pct_chg", 0)}
        for s in stocks[:30]
    ], "count": len(stocks)}


def _exec_market_data(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.data_collector import get_stock_market_data
    md = get_stock_market_data(str(args.get("code", "")).strip(), days=int(args.get("days", 20) or 20))
    return {
        "code": str(args.get("code", "")),
        "closes": [round(float(c), 2) for c in (md.closes or [])][-20:],
        "pct_chg_5d": round(float(md.pct_chg_5d or 0), 4),
        "volume_trend": round(float(md.volume_trend or 0), 4),
        "volatility": round(float(md.volatility or 0), 4),
        "drawdown": round(float(md.drawdown or 0), 4),
        "bars": len(md.closes or []),
    }


def _exec_financials(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.data_collector import get_stock_financials
    fin = get_stock_financials(str(args.get("code", "")).strip())
    return {
        "code": str(args.get("code", "")),
        "pe": round(float(fin.pe or 0), 2),
        "pb": round(float(fin.pb or 0), 2),
        "roe": round(float(fin.roe or 0), 2) if fin.roe else None,
        "pe_percentile": round(float(fin.pe_percentile or 0.5), 3),
        "revenue_growth": fin.revenue_growth,
        "profit_growth": fin.profit_growth,
    }


def _exec_news(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.data_collector import get_stock_news
    news = get_stock_news(str(args.get("code", "")).strip(), days=int(args.get("days", 3) or 3))
    return {"news": [
        {
            "title": _truncate_text(n.title, 120),
            "content": _truncate_text(n.content, 250),
            "source": n.source,
            "published_at": n.published_at,
        }
        for n in news[:8]
    ], "count": len(news)}


def _exec_risk(args: Dict[str, Any]) -> Dict[str, Any]:
    from types import SimpleNamespace
    from src.data_collector import get_stock_market_data, get_stock_financials
    from src.risk_analyzer import analyze_risk, _metrics_from_closes

    code = str(args.get("code", "")).strip()
    md = get_stock_market_data(code, days=20)
    fin = get_stock_financials(code, allow_live=False)
    # 快路径: 东财行情(closes) + 缓存财务, 绕开 akshare 慢接口
    if len(md.closes or []) >= 5:
        m = _metrics_from_closes(md.closes)
        if m is not None:
            vol, dd = m
            pe_pct = float(getattr(fin, "pe_percentile", 0.5) or 0.5)
            from config import RISK_LOW_VOL, RISK_LOW_DRAWDOWN, RISK_LOW_PE_PCT, RISK_MID_VOL, RISK_MID_DRAWDOWN
            if vol < RISK_LOW_VOL and dd < RISK_LOW_DRAWDOWN and pe_pct < RISK_LOW_PE_PCT:
                level = "低"
            elif vol < RISK_MID_VOL and dd < RISK_MID_DRAWDOWN:
                level = "中"
            else:
                level = "高"
            return {
                "code": code,
                "risk_level": level,
                "volatility": round(vol, 4),
                "max_drawdown": round(dd, 4),
                "valuation_risk": "低" if pe_pct < 0.4 else ("中" if pe_pct < 0.7 else "高"),
                "detail": f"波动率{vol:.1%}, 近20日最大回撤{dd:.1%}, 基于东财实时行情",
            }
    # 兜底: 完整 analyze_risk (含 akshare)
    stock = SimpleNamespace(code=code, name="", market=md, financials=fin)
    risk = analyze_risk(stock)
    return {
        "code": code,
        "risk_level": risk.get("risk_level"),
        "volatility": risk.get("volatility"),
        "max_drawdown": risk.get("max_drawdown"),
        "valuation_risk": risk.get("valuation_risk"),
        "detail": _truncate_text(risk.get("detail", ""), 200),
    }


def _exec_topic_news(args: Dict[str, Any]) -> Dict[str, Any]:
    import json as _json
    from pathlib import Path

    topic = str(args.get("topic", "")).strip()
    cache_path = Path(__file__).resolve().parent.parent / "data" / "news_cache.json"
    try:
        with open(cache_path, encoding="utf-8") as f:
            cache = _json.load(f)
        topics = cache.get("topics", {})
        news = topics.get(topic) or []
        if not news:  # 别名匹配
            for k, v in topics.items():
                if topic and (topic in k or k in topic):
                    news = v
                    break
        return {
            "topic": topic,
            "generated_at": cache.get("generated_at", ""),
            "news": news[:6],
            "count": len(news),
        }
    except (OSError, _json.JSONDecodeError) as e:
        return {"topic": topic, "news": [], "count": 0, "error": f"新闻缓存不可用: {str(e)[:80]}"}


def _exec_list_topics(args: Dict[str, Any]) -> Dict[str, Any]:
    from config import OFFLINE_TOPICS, OFFLINE_FILES
    return {"topics": OFFLINE_TOPICS, "files": OFFLINE_FILES}


_EXECUTORS: Dict[str, Any] = {
    "get_topic_news": _exec_topic_news,
    "parse_event": _exec_parse_event,
    "deduce_industry_chain": _exec_deduce_chain,
    "find_matching_concepts": _exec_find_concepts,
    "get_concept_stocks": _exec_concept_stocks,
    "get_stock_market_data": _exec_market_data,
    "get_stock_financials": _exec_financials,
    "get_stock_news": _exec_news,
    "get_stock_risk": _exec_risk,
    "list_offline_topics": _exec_list_topics,
}


def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """执行工具, 返回可序列化结果。未知工具/执行异常返回 {"error": ...}。"""
    if name not in _EXECUTORS:
        return {"error": f"未知工具: {name}", "available": tool_names()}
    try:
        result = _EXECUTORS[name](args or {})
        if not isinstance(result, dict):
            result = {"result": result}
        return result
    except Exception as e:  # noqa: BLE001 - 工具失败回填给 LLM 让其换策略
        logger.warning("工具 %s 执行失败: %s", name, str(e)[:120])
        return {"error": f"{name} 执行失败: {str(e)[:150]}", "hint": "请尝试其他工具或修改参数"}


def tool_result_text(name: str, args: Dict[str, Any]) -> str:
    """执行工具并返回紧凑文本 (用于 trace 展示)。"""
    try:
        return _safe_json(execute_tool(name, args), limit=2000)
    except Exception as e:  # noqa: BLE001
        return _safe_json({"error": str(e)[:100]}, limit=300)
