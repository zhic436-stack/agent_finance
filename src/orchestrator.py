# -*- coding: utf-8 -*-
"""ReAct 编排器: 让 LLM 自主调用金融工具完成主题研究 (真 Agent 路径)。

与 src/pipeline.py 的关系:
- pipeline.run_analysis(use_agent=True) 先走本模块; 失败或 LLM 不可用时自动降级回旧固定流程。
- 输出结构兼容 run_analysis: event/chain/concepts/stock_results/report/trace/errors + _from_agent=True。

Agent 行为:
  1. LLM 根据目标自主选择工具 (parse_event -> 产业链 -> 概念 -> 行情/财务/新闻/风险)
  2. 每步工具结果回填给 LLM, 模型据此决定下一步
  3. 无需再调用工具时, 模型输出最终研究 JSON (结论 + 关键股票 + 报告)
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_STEPS = 6

SYSTEM_PROMPT = """你是金融研究 Agent, 负责对一个热点主题做事件驱动研究。你可以调用一组金融工具自主收集信息:
- 先 parse_event 理解事件, 再 deduce_industry_chain 推导产业链, 再 find_matching_concepts 找概念板块
- 用 get_concept_stocks 或 list_offline_topics 确定候选股票池
- 对重点股票用 get_stock_market_data / get_stock_financials / get_stock_news / get_stock_risk 逐一核实
收敛规则 (必须遵守, 这是硬性时间约束):
1. 重点股票只选 3 只: 每只最多查 1 个工具 (优先 get_stock_risk 或 get_stock_market_data), 不要查新闻。
2. 全流程最多 3 轮工具收集 (第 1 轮: 事件+产业链; 第 2 轮: 概念+成分股; 第 3 轮: 3 只股票数据)。
3. 第 4 轮必须输出最终 JSON。信息足以支撑报告即可停止, 追求时效而非穷尽数据; 缺失数据直接标注'数据暂缺', 不要重试。
4. 工具结果可能标注 error, 遇到时换参数或换工具, 不要编造数据。
5. 当信息足够时, 停止调用工具, 输出最终 JSON (不要用 markdown 代码块包裹):
{
  "summary": "一句话研究结论",
  "event": {"topic": "主题", "event_type": "政策/行业/公司/其他", "benefited_industries": ["..."], "keywords": ["..."]},
  "chain": [{"name": "环节名", "position": "上游/中游/下游", "transmission": "传导逻辑"}],
  "concepts": ["概念板块名"],
  "key_stocks": [
    {"code": "6位代码", "name": "股票名", "rationale": "入选理由",
     "factors": {"event": 0-100, "value": 0-100, "growth": 0-100, "market": 0-100, "composite": 0-100},
     "risk_level": "低/中/高/数据暂缺"}
  ],
  "risk_notes": "整体风险提示, 1-2 句",
  "report_md": "完整 Markdown 研究报告, 含: 事件解读、产业链分析、候选股与理由、风险提示、免责声明"
}
4. 研究报告必须基于工具查到的真实数据, 数字与工具结果一致, 不得虚构行情或财务数字。
"""


def run_agent_research(
    topic: str,
    max_steps: int = MAX_STEPS,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """ReAct 编排。返回 run_analysis 兼容结构 (带 _from_agent=True)。失败返回 {"ok": False}。"""
    t0 = time.time()
    trace: List[Dict[str, Any]] = []
    errors: List[str] = []
    topic = (topic or "").strip()
    if not topic:
        return {"ok": False, "error": "主题为空"}

    def _trace(step: str, detail: str = "", elapsed: float = 0.0, status: str = "ok") -> None:
        trace.append({
            "step": step, "detail": detail,
            "elapsed_ms": int(elapsed * 1000), "status": status,
        })

    if not use_llm:
        return {"ok": False, "error": "use_llm=False 时不走 Agent 路径"}

    try:
        from src.llm import chat_completion_with_tools
        from src.agent_tools import get_tool_schemas, execute_tool, tool_result_text
        from config import ZHIPU_API_KEY
    except ImportError as e:
        return {"ok": False, "error": f"Agent 依赖缺失: {e}"}
    # 提供方: 配置了智谱 key 时优先用智谱 (响应快, 保证稳定收敛), 否则昇腾
    llm_provider = "zhipu" if ZHIPU_API_KEY else "ascend"
    if llm_provider == "zhipu":
        logger.info("Agent 使用智谱提供方 (glm-4-flash, 快速收敛)")
    else:
        logger.info("Agent 使用昇腾提供方")


    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"请研究热点主题: 【{topic}】\n"
            "目标: 识别事件类型、推导受益产业链、确定概念板块、找出 3 只重点受益股票并核实行情/风险, "
            "然后立即输出研究结论与 Markdown 研究报告。不要过度收集数据。"
        )},
    ]

    tool_calls_used = 0
    for step_i in range(max_steps):
        _t = time.time()
        resp = chat_completion_with_tools(
            messages, tools=get_tool_schemas(),
            temperature=0.2, max_tokens=1024,
            retries=1, timeout=90, model=None, provider=llm_provider,
        )
        if resp is None:
            # 中间轮失败: 基于已有数据尝试总结降级, 保证有产出
            errors.append("LLM 调用失败, 尝试基于已收集数据总结")
            resp2 = chat_completion_with_tools(
                messages + [{"role": "user", "content": "请基于以上工具数据, 立即输出最终研究 JSON (格式同上)。"}],
                tools=None, temperature=0.1, max_tokens=2048, retries=0, timeout=120, provider=llm_provider,
            )
            if resp2:
                content2 = resp2.get("content") or ""
                final = _parse_final(content2)
                if final is not None:
                    return _build_result(topic, final, trace, errors, t0, tool_calls_used)
                return _build_report_fallback(topic, content2, messages, trace, errors, t0, tool_calls_used)
            break
        content = resp.get("content") or ""
        tool_calls = resp.get("tool_calls") or []

        if not tool_calls:
            # 模型认为信息足够 -> 解析最终 JSON
            final = _parse_final(content)
            if final is None and step_i < max_steps - 1:
                # 输出不是合法 JSON, 回填错误让其修正
                messages.append({"role": "user", "content": "你的最终输出不是合法 JSON, 请只输出合规 JSON (不要 markdown 代码块)。"})
                continue
            if final is None:
                # 最后一轮且输出非 JSON: 内容降级为报告 (保证必有产出)
                logger.warning("Agent 最终 JSON 解析失败(最后轮), 降级为报告模式")
                return _build_report_fallback(topic, content, messages, trace, errors, t0, tool_calls_used)
            return _build_result(topic, final, trace, errors, t0, tool_calls_used)

        # 最后一轮强制收敛: 不带工具, 基于全部上下文生成最终 JSON (保证不超预算/必收敛)
        if step_i == max_steps - 1:
            resp2 = chat_completion_with_tools(
                messages + [{"role": "user", "content": "请基于以上工具收集的数据, 立即输出最终研究 JSON (格式同上, 不要 markdown 代码块)。"}],
                tools=None, temperature=0.1, max_tokens=2048, retries=0, timeout=120, provider=llm_provider,
            )
            if resp2:
                content2 = resp2.get("content") or ""
                final = _parse_final(content2)
                if final is not None:
                    return _build_result(topic, final, trace, errors, t0, tool_calls_used)
                # 降级: 总结文本直接作为报告, 股票从工具调用历史提取 (保证 ok=True)
                logger.warning("Agent 最终 JSON 解析失败, 降级为报告模式")
                return _build_report_fallback(topic, content2, messages, trace, errors, t0, tool_calls_used)
            errors.append("最终总结调用失败")
            break

        # 执行工具调用 (并行): assistant 消息只保留将被执行的调用 (与执行结果一致)
        exec_calls = tool_calls[:4]  # 单轮最多执行 4 个工具
        messages.append({"role": "assistant", "content": content, "tool_calls": exec_calls})

        def _run_one(tc):
            try:
                fn = tc.get("function", {}).get("name", "")
                raw_args = tc.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                _te = time.time()
                result = execute_tool(fn, args)
                _trace(f"Agent 调用: {fn}", f"参数 {tool_result_text(fn, args)[:120]}", time.time() - _te)
                return (tc.get("id", f"call_{step_i}_{tool_calls_used}"), result)
            except Exception as e:  # noqa: BLE001
                logger.warning("Agent 工具执行异常: %s", str(e)[:120])
                return (tc.get("id", f"call_{step_i}_{tool_calls_used}"), {"error": str(e)[:150]})

        tool_results = []
        if len(exec_calls) > 1:
            try:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=len(exec_calls)) as pool:
                    tool_results = list(pool.map(_run_one, exec_calls))
            except Exception:  # noqa: BLE001 - 并行失败降级串行
                tool_results = [_run_one(tc) for tc in exec_calls]
        else:
            tool_results = [_run_one(exec_calls[0])] if exec_calls else []
        tool_calls_used += len(tool_results)
        for tc_id, result in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:800],
            })

    errors.append(f"达到最大步骤 {max_steps}, Agent 未收敛")
    return {"ok": False, "error": errors[-1], "trace": trace, "elapsed_ms": int((time.time() - t0) * 1000)}


def _parse_final(content: str) -> Optional[Dict[str, Any]]:
    """解析模型最终输出为 dict。容忍代码块围栏/前后噪声/轻微格式错误。"""
    import json as _json
    import re

    if not content:
        return None
    text = content.strip()

    # 1. 常规清洗 (代码块围栏 + 截取 JSON + json_repair)
    from src.llm import _clean_json
    result = _clean_json(text)
    if result is not None:
        return result

    # 2. 手工兜底: 去围栏 + 截取最外层 { }
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.M)
    text = re.sub(r"\s*```$", "", text, flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    try:
        return _json.loads(text)
    except _json.JSONDecodeError:
        pass

    # 3. json_repair 终极兜底
    try:
        from json_repair import repair_json
        fixed = repair_json(text)
        if fixed and fixed != text:
            return _json.loads(fixed)
    except Exception:  # noqa: BLE001
        pass
    logger.warning("Agent 最终输出无法解析为 JSON, 前 300 字: %s", content[:300])
    return None


def _build_report_fallback(topic, report_text, messages, trace, errors, t0, tool_calls_used) -> Dict[str, Any]:
    """降级路径: 总结文本作为报告, 股票代码从工具调用历史提取。保证 Agent 路径必有产出。"""
    import re as _re
    from types import SimpleNamespace

    text = (report_text or "").strip()
    text = _re.sub(r"^```(?:markdown)?\s*", "", text, flags=_re.M)
    text = _re.sub(r"\s*```$", "", text, flags=_re.M)

    codes: List[str] = []
    for m in messages:
        if m.get("role") == "tool":
            try:
                data = json.loads(m.get("content") or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                data = {}
            c = data.get("code") if isinstance(data, dict) else None
            if c and _re.fullmatch(r"\d{6}", str(c)) and str(c) not in codes:
                codes.append(str(c))

    stock_results = [
        {"stock": SimpleNamespace(code=c, name=""), "factors": {}, "risk": {}}
        for c in codes[:10]
    ]
    return {
        "ok": True,
        "topic": topic,
        "event": {"topic": topic, "event_type": "其他", "benefited_industries": [], "keywords": []},
        "chain": [], "hypothesis": {}, "concepts": [],
        "stock_results": stock_results,
        "report": text or f"# {topic} 研究报告\n\n> Agent 已收集数据但未能生成完整报告。",
        "summary": "", "risk_notes": "",
        "elapsed_ms": int((time.time() - t0) * 1000),
        "llm_calls": tool_calls_used,
        "data_sources": {"agent_tools": tool_calls_used},
        "trace": trace, "errors": errors,
        "_from_agent": True, "_report_only": True,
    }


def _build_result(topic, final, trace, errors, t0, tool_calls_used) -> Dict[str, Any]:
    """把 agent 最终 JSON 转成 run_analysis 兼容结构。"""
    elapsed_ms = int((time.time() - t0) * 1000)
    if final is None or not isinstance(final, dict):
        return {"ok": False, "error": "Agent 最终输出解析失败", "trace": trace, "elapsed_ms": elapsed_ms}

    from types import SimpleNamespace

    stock_results = []
    for ks in (final.get("key_stocks") or [])[:15]:
        code = str(ks.get("code", "") or "").strip()
        name = str(ks.get("name", "") or "")
        if not code:
            continue
        factors = {
            "event": round(float(ks.get("factors", {}).get("event", 0) or 0), 1),
            "value": round(float(ks.get("factors", {}).get("value", 0) or 0), 1),
            "growth": round(float(ks.get("factors", {}).get("growth", 0) or 0), 1),
            "market": round(float(ks.get("factors", {}).get("market", 0) or 0), 1),
        }
        factors["composite"] = round(float(ks.get("factors", {}).get("composite", 0) or 0), 1)
        risk = {
            "risk_level": ks.get("risk_level", "未知") or "未知",
            "volatility": None, "max_drawdown": None,
            "valuation_risk": "未知",
            "detail": str(ks.get("rationale", "") or ""),
        }
        stock = SimpleNamespace(code=code, name=name)
        stock_results.append({"stock": stock, "factors": factors, "risk": risk})

    event = final.get("event") or {"topic": topic, "event_type": "其他", "benefited_industries": [], "keywords": []}
    if not isinstance(event, dict):
        event = {"topic": topic, "event_type": "其他", "benefited_industries": [], "keywords": []}
    event.setdefault("topic", topic)

    return {
        "ok": True,
        "topic": topic,
        "event": event,
        "chain": final.get("chain") or [],
        "hypothesis": {},
        "concepts": final.get("concepts") or [],
        "stock_results": stock_results,
        "report": final.get("report_md") or f"# {topic} 研究报告\n\n> Agent 未生成完整报告。",
        "summary": final.get("summary", ""),
        "risk_notes": final.get("risk_notes", ""),
        "elapsed_ms": elapsed_ms,
        "llm_calls": tool_calls_used,
        "data_sources": {"agent_tools": tool_calls_used},
        "trace": trace,
        "errors": errors,
        "_from_agent": True,
    }
