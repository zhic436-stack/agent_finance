"""全链路编排层: 输入热点 -> 完整研究结果。

串联各冻结模块, 提供 UI / 集成测试 / demo_prep 共用的 run_analysis()。
本模块不修改任何冻结 API, 只做流程编排与逐级降级。

流程:
  热点 topic
    -> parse_event           事件解析
    -> deduce_industry_chain 产业链推理
    -> find_matching_concepts 概念映射
    -> load_offline_stocks   候选股加载(离线包, 保底)
    -> compute_all_factors_batch 四因子
    -> analyze_risk_batch    风险分析
    -> generate_report       报告生成

失败逐级降级: 每一环失败都返回"友好空态", 不抛异常。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def run_analysis(topic: str, max_candidates: int = 30, use_llm: bool = True,
                 enrich_market: bool = False, use_agent: bool = False) -> Dict[str, Any]:
    """执行完整分析链路, 返回结构化结果。任何环节失败不抛异常。

    参数:
        topic: 热点主题
        max_candidates: 候选股上限
        use_llm: 报告是否尝试 LLM 润色
        enrich_market: 是否实时拉行情补充市场因子 (默认 False 离线可复现;
                       True 时每只候选股调 get_stock_market_data, 慢且可能限流)
        use_agent: 是否走 ReAct Agent 路径 (LLM 自主调用工具研究);
                   Agent 失败或 LLM 不可用时自动降级回固定流程

    返回:
        {
            "topic": str,
            "event": parse_event 输出,
            "chain": 产业链环节列表,
            "concepts": 命中的东财概念,
            "stock_results": [{"stock": StockProfile, "factors": {...}, "risk": {...}}, ...],
            "report": Markdown 报告,
            "elapsed_ms": 总耗时(毫秒),
            "errors": [环节错误描述, ...],
        }
    """
    t0 = time.time()
    errors: List[str] = []
    topic = (topic or "").strip()

    # 重置昇腾调用计数 (成本控制)
    try:
        from src.llm import reset_call_count
        reset_call_count()
    except ImportError:
        pass

    # 0. Agent 路径 (可选): LLM 自主调用金融工具研究。失败自动降级回固定流程。
    if use_agent:
        try:
            from src.orchestrator import run_agent_research
            agent_result = run_agent_research(topic, use_llm=use_llm)
            if agent_result.get("ok"):
                agent_result.setdefault("elapsed_ms", int((time.time() - t0) * 1000))
                return agent_result
            errors.append("Agent路径失败, 降级固定流程: " + str(agent_result.get("error", ""))[:80])
        except Exception as e:  # noqa: BLE001
            errors.append("Agent路径异常, 降级固定流程: " + str(e)[:80])
        # 给固定流程完整 LLM 预算 (agent 可能已消耗部分)
        try:
            from src.llm import reset_call_count
            reset_call_count()
        except ImportError:
            pass

    # 执行轨迹记录 (C3: 供 UI 展示研究过程)
    trace: List[Dict[str, Any]] = []

    def _trace(step: str, detail: str = "", elapsed: float = 0.0, status: str = "ok") -> None:
        trace.append({
            "step": step,
            "detail": detail,
            "elapsed_ms": int(elapsed * 1000),
            "status": status,
        })

    # 1. 事件解析
    _t1 = time.time()
    try:
        from src.event_analyzer import parse_event
        event = parse_event(topic)
        _trace("事件理解", f"识别为{event.get('event_type', '其他')}事件", time.time() - _t1)
    except Exception as e:  # noqa: BLE001
        errors.append(f"事件解析: {str(e)[:80]}")
        event = {"topic": topic, "event_type": "其他", "benefited_industries": [], "keywords": []}
        _trace("事件理解", "失败, 走兜底", time.time() - _t1, "warn")

    # 2. 产业链推理
    _t2 = time.time()
    try:
        from src.event_analyzer import deduce_industry_chain
        chain = deduce_industry_chain(event)
        _trace("产业链推理", f"识别{len(chain)}个受益环节", time.time() - _t2)
    except Exception as e:  # noqa: BLE001
        errors.append(f"产业链推理: {str(e)[:80]}")
        chain = []
        _trace("产业链推理", "失败, 走兜底", time.time() - _t2, "warn")

    # 2.5 研究假设 (事件 -> 可验证假设)
    hypothesis: Dict[str, Any] = {}
    _t25 = time.time()
    try:
        from src.hypothesis_generator import generate_hypothesis
        hypothesis = generate_hypothesis(event, use_llm=use_llm)
        _trace("研究假设", "生成因果逻辑与传播路径", time.time() - _t25)
    except Exception as e:  # noqa: BLE001
        errors.append(f"研究假设: {str(e)[:80]}")
        _trace("研究假设", "失败, 走兜底", time.time() - _t25, "warn")

    # 3. 概念映射
    try:
        from src.event_analyzer import find_matching_concepts
        concepts = find_matching_concepts(chain)
    except Exception as e:  # noqa: BLE001
        errors.append(f"概念映射: {str(e)[:80]}")
        concepts = []

    # 4. 候选股: 优先离线包 (保底), 数量不足再尝试实时
    stocks: List[Any] = []
    try:
        from src.data_collector import load_offline_stocks, StockInfo

        # 候选主题: 原始 topic 优先 (确保预置主题必命中), 再补 LLM 扩展行业
        candidate_industries = list(dict.fromkeys(
            [topic] + (event.get("benefited_industries") or [])
        ))
        for ind in candidate_industries:
            for s in load_offline_stocks(ind):
                # 离线包是"按主题"的: 成分股天然属于该主题概念
                # 给 StockInfo 标注 concepts (calc_event_factor 依赖它)
                s.concepts = [ind]  # type: ignore[attr-defined]
                stocks.append(s)
        # 去重
        seen = set()
        stocks = [s for s in stocks if not (s.code in seen or seen.add(s.code))]
        stocks = stocks[:max_candidates]

        # If offline stocks insufficient, try realtime screening
        if len(stocks) < 5 and enrich_market:
            try:
                from src.real_screener import screen_realtime_stocks
                realtime = screen_realtime_stocks(topic, event, max_candidates - len(stocks))
                existing_codes = {s.code for s in stocks}
                for r in realtime:
                    if r["code"] not in existing_codes:
                        s = StockInfo(
                            code=r["code"],
                            name=r.get("name", ""),
                            price=float(r.get("price", 0) or 0),
                            pct_chg=float(r.get("pct_chg", 0) or 0),
                        )
                        s.concepts = [topic]
                        stocks.append(s)
            except Exception:
                pass  # Realtime screening is best-effort
    except Exception as e:  # noqa: BLE001
        errors.append(f"候选股加载: {str(e)[:80]}")

    # 4.5 行情补充: 为市场因子/风险分析构造 MarketData (并行化, C2)。
    #     enrich_market=True: 多源拉取 (东财->新浪->缓存), 并发 CONCURRENT_LIMIT
    #     enrich_market=False: 纯离线 pct_chg 近似 (快速/确定)
    if stocks:
        from src.data_collector import MarketData

        source_stats: dict = {}

        def _fetch_market(s):
            """单只股票行情拉取 (含多源降级)。返回 (stock, md, source)。"""
            if enrich_market:
                from src.data_sources import get_market_data_multi
                return s, *get_market_data_multi(s.code)
            return s, None, "离线缓存"

        def _apply_market(item):
            """应用行情到股票 (主线程, 避免线程竞争)。"""
            s, md, source = item
            if md and getattr(md, "closes", None):
                s.market = md
            else:
                pct = float(getattr(s, "pct_chg", 0.0) or 0.0) / 100.0
                s.market = MarketData(
                    pct_chg_5d=pct,
                    volume_trend=0.5,
                    volatility=abs(pct) * 0.5,
                    drawdown=max(0.0, -pct),
                    closes=[], volumes=[],
                )
            s.data_source = source  # type: ignore[attr-defined]
            return s

        # 并行拉取行情
        if enrich_market and len(stocks) > 1:
            try:
                from concurrent.futures import ThreadPoolExecutor
                from config import CONCURRENT_LIMIT
                with ThreadPoolExecutor(max_workers=CONCURRENT_LIMIT) as pool:
                    fetched = list(pool.map(_fetch_market, stocks))
            except Exception as e:  # noqa: BLE001 - 并行失败降级串行
                logger.warning("并行行情拉取失败, 降级串行: %s", str(e)[:80])
                fetched = [_fetch_market(s) for s in stocks]
        else:
            fetched = [_fetch_market(s) for s in stocks]

        # 应用行情
        stocks = [_apply_market(item) for item in fetched]

        # 4.6 财务数据补充: 读预采集 financial_cache 填充 PE/PB (只读缓存, 不触发网络)
        # 修复: 此前价值/成长因子拿不到真实财务输入 (get_stock_profile 无调用点)
        try:
            from src.data_collector import get_stock_financials
            for s in stocks:
                if getattr(s, "financials", None) is None:
                    s.financials = get_stock_financials(s.code, allow_live=False)
        except Exception as e:  # noqa: BLE001 - 财务补充失败不阻断主流程
            logger.warning("财务数据补充失败: %s", str(e)[:80])

        # 来源统计
        for s in stocks:
            src = getattr(s, "data_source", "离线缓存")
            source_stats[src] = source_stats.get(src, 0) + 1

    # 5. 因子计算
    stock_results: List[Dict[str, Any]] = []
    _t5 = time.time()
    try:
        from src.factor_engine import compute_all_factors_batch
        factor_results = compute_all_factors_batch(stocks, event)
        stock_results = [{"stock": fr["stock"], "factors": fr["factors"], "risk": {}} for fr in factor_results]
        _trace("因子分析", f"计算{len(stock_results)}只候选股四因子", time.time() - _t5)
    except Exception as e:  # noqa: BLE001
        errors.append(f"因子计算: {str(e)[:80]}")
        _trace("因子分析", "失败, 返回0分", time.time() - _t5, "warn")

    # 6. 风险分析
    _t6 = time.time()
    try:
        from src.risk_analyzer import analyze_risk_batch
        risk_results = analyze_risk_batch(stocks)
        risk_map = {r["stock"].code: r["risk"] for r in risk_results}
        for sr in stock_results:
            sr["risk"] = risk_map.get(sr["stock"].code, {})
        _trace("风险分析", f"评估{len(stock_results)}只候选股风险", time.time() - _t6)
    except Exception as e:  # noqa: BLE001
        errors.append(f"风险分析: {str(e)[:80]}")
        _trace("风险分析", "失败, 按高风险处理", time.time() - _t6, "warn")

    # 7. 报告生成
    report = ""
    _t7 = time.time()
    try:
        from src.report_generator import generate_report
        report = generate_report(event, chain, stock_results, use_llm=use_llm)
        _trace("报告生成", f"生成{len(report)}字研究报告", time.time() - _t7)
    except Exception as e:  # noqa: BLE001
        errors.append(f"报告生成: {str(e)[:80]}")
        report = f"# {topic} 研究报告\n\n> 报告生成失败, 请稍后重试。"
        _trace("报告生成", "失败, 输出占位报告", time.time() - _t7, "warn")

    elapsed_ms = int((time.time() - t0) * 1000)
    # 统计昇腾调用次数
    llm_calls = 0
    try:
        from src.llm import get_call_count
        llm_calls = get_call_count()
    except ImportError:
        pass
    # 数据来源统计
    source_stats = {}
    for sr in stock_results:
        src = getattr(sr.get("stock"), "data_source", "离线缓存")
        source_stats[src] = source_stats.get(src, 0) + 1
    return {
        "topic": topic,
        "event": event,
        "chain": chain,
        "hypothesis": hypothesis,
        "concepts": concepts,
        "stock_results": stock_results,
        "report": report,
        "elapsed_ms": elapsed_ms,
        "llm_calls": llm_calls,
        "data_sources": source_stats,
        "trace": trace,
        "errors": errors,
    }


def prepare_topic_stocks(topic: str) -> List[Any]:
    """仅加载候选股 (demo_prep / 页面复用)。失败返回空列表。"""
    try:
        from src.data_collector import load_offline_stocks
        stocks = load_offline_stocks(topic)
        seen = set()
        return [s for s in stocks if not (s.code in seen or seen.add(s.code))]
    except Exception as e:  # noqa: BLE001
        logger.warning("候选股加载失败 %s: %s", topic, str(e)[:80])
        return []


def load_demo_state(topic: str) -> Dict[str, Any]:
    """从 demo_state.json 加载预计算结果 (预置热点一键加载)。

    demo_prep 生成: data/demo_state.json, 含4个预置热点的完整结果
    (事件/产业链/概念/因子/风险/报告, 因子含固化行情)。

    返回与 run_analysis 相同的结构; 未命中返回空 dict。
    """
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "demo_state.json"
    try:
        import json
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        data = state.get("topics", {}).get(topic)
        if not data:
            return {}
        event = data.get("event", {})
        chain = data.get("chain") or []
        if not chain:
            from src.event_analyzer import deduce_industry_chain
            chain = deduce_industry_chain(event)
        stock_results = [
            {"stock": _stock_from_dict(stock), "factors": stock.get("factors", {}), "risk": stock.get("risk", {})}
            for stock in data.get("stock_results", [])
        ]
        from src.report_generator import generate_report
        report = generate_report(event, chain, stock_results, use_llm=False)
        return {
            "topic": topic,
            "event": event,
            "chain": chain,
            "hypothesis": data.get("hypothesis", {}),
            "concepts": data.get("concepts", []),
            "stock_results": stock_results,
            "report": report,
            "elapsed_ms": data.get("elapsed_ms", 0),
            "errors": data.get("errors", []),
            "_from_demo": True,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("demo_state 加载失败 %s: %s", topic, str(e)[:80])
        return {}


def _stock_from_dict(d: Dict[str, Any]):
    """从 dict 还原 StockProfile 轻量对象 (仅 UI 展示需要的字段)。"""
    from types import SimpleNamespace
    return SimpleNamespace(
        code=d.get("code", ""),
        name=d.get("name", ""),
        price=d.get("price"),
        pct_chg=d.get("pct_chg"),
    )


# ============ 高层封装 (冲刺包 Phase 2 补充) ============


def run_analysis_cached(topic: str, **kwargs) -> Dict[str, Any]:
    """缓存版分析: 优先 demo_state, 未命中实时分析。

    预热/演示路径用。命中返回 _from_demo=True, 未命中实时跑并缓存。
    """
    cached = load_demo_state(topic)
    if cached:
        return cached
    return run_analysis(topic, **kwargs)


def compare_topics(topics: list, **kwargs) -> Dict[str, Any]:
    """多话题对比分析: 各话题 Top 股票综合分对比。

    返回: {"topics": {topic: {"stocks": n, "top_score": float, "avg_score": float}}, "ranking": [...]}
    """
    ranking = []
    details = {}
    for topic in topics:
        try:
            r = run_analysis_cached(topic, use_llm=False, max_candidates=10, enrich_market=False, **kwargs)
            comps = [sr["factors"].get("composite", 0) for sr in r.get("stock_results", [])]
            stats = {
                "stocks": len(comps),
                "top_score": round(max(comps), 1) if comps else 0.0,
                "avg_score": round(sum(comps) / len(comps), 1) if comps else 0.0,
            }
            details[topic] = stats
            ranking.append({"topic": topic, **stats})
        except Exception as e:  # noqa: BLE001
            details[topic] = {"stocks": 0, "top_score": 0.0, "avg_score": 0.0, "error": str(e)[:60]}
            ranking.append({"topic": topic, "stocks": 0, "top_score": 0.0, "avg_score": 0.0})
    ranking.sort(key=lambda x: x.get("top_score", 0), reverse=True)
    return {"topics": details, "ranking": ranking}


def aggregate_topics(topics: list, **kwargs) -> Dict[str, Any]:
    """多话题聚合: 合并候选股, 去重, 统计跨话题覆盖。

    返回: {"total_stocks": int, "unique_codes": int, "overlap": {code: [topics]}, "by_topic": {...}}
    """
    from collections import defaultdict

    code_topics = defaultdict(list)
    by_topic = {}
    for topic in topics:
        try:
            r = run_analysis_cached(topic, use_llm=False, max_candidates=10, enrich_market=False, **kwargs)
            codes = [sr["stock"].code for sr in r.get("stock_results", []) if sr.get("stock")]
            by_topic[topic] = {"count": len(codes)}
            for c in codes:
                code_topics[c].append(topic)
        except Exception as e:  # noqa: BLE001
            by_topic[topic] = {"count": 0, "error": str(e)[:60]}

    overlap = {c: t for c, t in code_topics.items() if len(t) > 1}
    return {
        "total_stocks": sum(v.get("count", 0) for v in by_topic.values()),
        "unique_codes": len(code_topics),
        "overlap_count": len(overlap),
        "overlap": dict(list(overlap.items())[:20]),
        "by_topic": by_topic,
    }
