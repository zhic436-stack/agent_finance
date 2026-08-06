"""四因子引擎 + 事件逻辑因子: 全部纯数学/规则计算, 不调用 LLM。

每个因子输出 0~100 归一化分数。
任一子项缺失时按 0 处理; 全部缺失时返回 0。

B3 新增三个事件逻辑因子:
- calc_event_strength: 事件强度 (政策等级 + 时效 + 关注度)
- calc_chain_position: 产业链位置 (直接/间接/情绪关联)
- calc_logic_certainty: 逻辑确定性 (落地/规划/概念)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from config import WEIGHTS, EVENT_LOGIC_WEIGHTS, POLICY_LEVEL_SCORE, EVENT_AGE_SCORES, LOGIC_CERTAINTY

logger = logging.getLogger(__name__)

# ============ 工具 ============


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _norm01(x: float, lo: float, hi: float) -> float:
    """将 x 线性映射到 0~1 (x 超出 [lo, hi] 截断)。"""
    if hi <= lo:
        return 0.0
    return _clamp((x - lo) / (hi - lo))


def _get_demo_financials(stock: Any):
    """演示数据兜底 (仅当 DEMO_DATA_FALLBACK 开启)。

    返回: {"value": float, "growth": float, "is_demo": True} 或 None (未开启/无代码)
    注意: 演示数据仅用于黑客松展示, 不代表真实财务数据。
    """
    from config import DEMO_DATA_FALLBACK

    if not DEMO_DATA_FALLBACK:
        return None
    code = getattr(stock, "code", "")
    if not code:
        return None
    try:
        from src.financial_demo_data import generate_financial_demo_data
        demo = generate_financial_demo_data(code, getattr(stock, "name", ""))
        # 用演示数据重算两个因子
        pe_pct = _clamp(demo["pe_percentile"])
        pb_pct = _clamp(demo["pb_percentile"])
        roe = max(0.0, float(demo["roe"]))
        value = (1.0 - pe_pct) * 0.4 + (1.0 - pb_pct) * 0.3 + _norm01(roe, 0.0, 30.0) * 0.3
        rev_score = _norm01(demo["revenue_growth"], -0.20, 0.50)
        prof_score = _norm01(demo["profit_growth"], -0.20, 0.50)
        growth = rev_score * 0.5 + prof_score * 0.5
        return {"value": value * 100, "growth": growth * 100, "is_demo": True}
    except Exception as e:  # noqa: BLE001
        logger.warning("演示数据生成失败 %s: %s", code, str(e)[:80])
        return None


# ============ 事件因子 ============


def calc_event_factor(stock: Any, event: Dict[str, Any]) -> float:
    """事件因子 = 概念匹配度 × 0.5 + 新闻覆盖度 × 0.5, 归一化 0~100。

    - 概念匹配度: stock.concepts 中命中 event 关键词/受益行业的比例
    - 新闻覆盖度: 该股近期新闻中命中事件关键词的比例
    任一数据缺失按 0 处理。
    """
    match_score = 0.0   # 概念匹配度 0~1
    news_score = 0.0    # 新闻覆盖度 0~1

    concepts = getattr(stock, "concepts", None) or []
    if concepts:
        keywords = set(event.get("keywords") or [])
        benefited = set(event.get("benefited_industries") or [])
        if keywords or benefited:
            hits = 0
            for c in concepts:
                if any(k and k in c for k in keywords) or any(b and b in c for b in benefited):
                    hits += 1
            match_score = hits / len(concepts)

    news = getattr(stock, "news", None) or []
    if news:
        keywords = event.get("keywords") or []
        if keywords:
            hit_news = 0
            for n in news:
                text = f"{getattr(n, 'title', '')}{getattr(n, 'content', '')}"
                if any(k and k in text for k in keywords):
                    hit_news += 1
            news_score = hit_news / len(news)

    return round((match_score * 0.5 + news_score * 0.5) * 100, 2)


# ============ 价值因子 ============


def calc_value_factor(stock: Any) -> float:
    """价值因子 = PE分位 × 0.4 + PB分位 × 0.3 + ROE × 0.3, 归一化 0~100。

    - PE分位: 越低越好 (估值越便宜) -> score = 1 - percentile
    - PB分位: 越低越好 -> score = 1 - percentile
    - ROE: 越高越好 -> 直接按 ROE/30 归一化 (30% 视为满分)
    数据缺失按 0 处理。
    """
    fin = getattr(stock, "financials", None)
    if not fin:
        # 无财务对象: 演示数据兜底 (仅当 DEMO_DATA_FALLBACK 开启)
        demo = _get_demo_financials(stock)
        if demo is None:
            return 0.0
        return round(demo["value"], 2)

    # 数据缺失判定: pe/pb/roe 全为 0 视为无财务数据
    has_real = bool(float(getattr(fin, "pe", 0.0) or 0.0) or float(getattr(fin, "pb", 0.0) or 0.0)
                    or float(getattr(fin, "roe", 0.0) or 0.0))
    if not has_real:
        # 演示数据兜底 (仅当 DEMO_DATA_FALLBACK 开启)
        demo = _get_demo_financials(stock)
        if demo is None:
            return 0.0
        return round(demo["value"], 2)

    pe_pct = _clamp(getattr(fin, "pe_percentile", 0.5))
    pb_pct = _clamp(getattr(fin, "pb_percentile", 0.5))
    roe = max(0.0, float(getattr(fin, "roe", 0.0) or 0.0))

    # 负 PE (亏损股): PE 分项按最差 (估值无意义)
    pe_val = float(getattr(fin, "pe", 0.0) or 0.0)
    if pe_val < 0:
        pe_pct = 1.0

    pe_score = 1.0 - pe_pct
    pb_score = 1.0 - pb_pct
    roe_score = _norm01(roe, 0.0, 30.0)   # 30% ROE 视为满分

    return round((pe_score * 0.4 + pb_score * 0.3 + roe_score * 0.3) * 100, 2)


# ============ 成长因子 ============


def calc_growth_factor(stock: Any) -> float:
    """成长因子 = 营收增长 × 0.5 + 利润增长 × 0.5, 归一化 0~100。

    增长率范围映射: -20% ~ +50% 线性映射到 0~1 (超过截断)。
    """
    fin = getattr(stock, "financials", None)
    if not fin:
        # 无财务对象: 演示数据兜底 (仅当 DEMO_DATA_FALLBACK 开启)
        demo = _get_demo_financials(stock)
        if demo is None:
            return 0.0
        return round(demo["growth"], 2)

    rev_g = float(getattr(fin, "revenue_growth", 0.0) or 0.0)
    prof_g = float(getattr(fin, "profit_growth", 0.0) or 0.0)

    # 数据缺失判定: 增长字段为 None 视为无财务数据
    has_real = not (getattr(fin, "revenue_growth", None) is None and getattr(fin, "profit_growth", None) is None)
    if not has_real:
        # 演示数据兜底 (仅当 DEMO_DATA_FALLBACK 开启)
        demo = _get_demo_financials(stock)
        if demo is None:
            return 0.0
        return round(demo["growth"], 2)

    rev_score = _norm01(rev_g, -0.20, 0.50)
    prof_score = _norm01(prof_g, -0.20, 0.50)

    return round((rev_score * 0.5 + prof_score * 0.5) * 100, 2)


# ============ 市场因子 ============


def calc_market_factor(stock: Any) -> float:
    """市场因子 = 5日涨跌幅 × 0.3 + 成交量变化 × 0.4 + 波动率 × 0.3, 归一化 0~100。

    - 5日涨跌幅: -10% ~ +10% 映射 0~1
    - 成交量变化: 已归一化 0~1 (0.5 为平量, 越高越放量)
    - 波动率: 5日收益率标准差, 0~0.05 映射 0~1 (越高越活跃)
    """
    md = getattr(stock, "market", None)
    if not md:
        return 0.0

    # 数据缺失判定: 无收盘价序列且无涨跌幅 -> 无行情数据
    if not getattr(md, "closes", None) and not float(getattr(md, "pct_chg_5d", 0.0) or 0.0):
        return 0.0

    pct5 = float(getattr(md, "pct_chg_5d", 0.0) or 0.0)
    vol_trend = _clamp(float(getattr(md, "volume_trend", 0.0) or 0.0))
    volatility = float(getattr(md, "volatility", 0.0) or 0.0)

    pct_score = _norm01(pct5, -0.10, 0.10)
    vol_score = vol_trend            # 已归一化
    vola_score = _norm01(volatility, 0.0, 0.05)

    return round((pct_score * 0.3 + vol_score * 0.4 + vola_score * 0.3) * 100, 2)


# ============ 事件逻辑因子 (B3 新增) ============


def calc_event_strength(event: Dict[str, Any]) -> float:
    """事件强度因子 (0-100): 政策等级 + 时效 + 市场关注度。

    - 政策等级: 国务院100/部委80/地方60/新闻20
    - 事件时效: 当天100/3天内80/7天内50/更久20
    - 市场关注度: 受益行业数 + 关键词数归一化
    事件缺失时返回 50 (中性)。
    """
    if not event:
        return 50.0

    # 1. 政策等级 (从事件文本/类型推断)
    topic = str(event.get("topic", ""))
    event_type = str(event.get("event_type", ""))
    policy_score = 20.0
    for kw, score in POLICY_LEVEL_SCORE.items():
        if kw in topic or kw in event_type:
            policy_score = max(policy_score, float(score))
    # 事件类型增强: 政策类事件政策分更高
    if "政策" in event_type or "政策" in topic:
        policy_score = max(policy_score, 80.0)

    # 2. 时效性: 无法确定事件时间, 用"近期"假设 (当天到3天内之间)
    #    demo/事件解析不含时间戳, 取中性偏积极 80
    age_score = 80.0

    # 3. 市场关注度: 受益行业数 + 关键词数
    industries = event.get("benefited_industries", []) or []
    keywords = event.get("keywords", []) or []
    attention = _clamp((len(industries) + len(keywords)) / 8.0) * 100

    strength = (policy_score * 0.4 + age_score * 0.3 + attention * 0.3)
    return round(strength, 2)


def calc_chain_position(stock: Any, event: Dict[str, Any]) -> float:
    """产业链位置因子 (0-100): 直接受益/间接受益/情绪关联。

    规则: 股票的 concepts 与事件受益行业匹配度决定位置。
    - 概念完全匹配核心行业: 100 (直接受益)
    - 概念含事件关键词: 70 (间接受益)
    - 仅概念板块相关: 30 (情绪关联)
    """
    concepts = getattr(stock, "concepts", None) or []
    if not concepts:
        return 30.0

    benefited = set(event.get("benefited_industries", []) or [])
    keywords = set(event.get("keywords", []) or [])

    # 直接命中受益行业 (核心环节)
    for c in concepts:
        if c in benefited:
            return 100.0
    # 概念含事件关键词 (间接受益)
    for c in concepts:
        if any(k and k in c for k in keywords):
            return 70.0
    # 仅相关 (情绪关联)
    return 30.0


def calc_logic_certainty(event: Dict[str, Any]) -> float:
    """逻辑确定性因子 (0-100): 政策已落地/规划/概念炒作。

    从事件文本推断确定性:
    - 含"发布/印发/落地/实施" -> 已落地 90
    - 含"规划/意见/方案/支持" -> 规划 60
    - 仅"概念/概念股/炒作" -> 概念 30
    """
    topic = str(event.get("topic", ""))
    event_type = str(event.get("event_type", ""))

    text = topic + event_type
    for kw, score in (("发布", 90), ("印发", 90), ("落地", 90), ("实施", 90),
                      ("规划", 60), ("意见", 60), ("方案", 60), ("支持", 60),
                      ("概念", 30), ("炒作", 30)):
        if kw in text:
            return float(score)
    # 默认: 行业事件偏规划阶段
    return 60.0 if "行业" in event_type else 50.0


def calc_event_logic_composite(event: Dict[str, Any], stock: Any) -> Dict[str, float]:
    """计算三个事件逻辑因子 + 加权综合。"""
    strength = calc_event_strength(event)
    position = calc_chain_position(stock, event)
    certainty = calc_logic_certainty(event)
    composite = (
        strength * EVENT_LOGIC_WEIGHTS["event_strength"]
        + position * EVENT_LOGIC_WEIGHTS["chain_position"]
        + certainty * EVENT_LOGIC_WEIGHTS["logic_certainty"]
    )
    return {
        "event_strength": round(strength, 2),
        "chain_position": round(position, 2),
        "logic_certainty": round(certainty, 2),
        "event_logic_composite": round(composite, 2),
    }


# ============ 综合得分 ============


def calc_composite_score(factors: Dict[str, float]) -> float:
    """加权综合得分: 事件30% + 价值25% + 成长25% + 市场20%。"""
    if not factors:
        return 0.0
    total = 0.0
    weight_sum = 0.0
    for key, weight in WEIGHTS.items():
        val = factors.get(key, 0.0)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = 0.0
        total += val * weight
        weight_sum += weight
    if weight_sum <= 0:
        return 0.0
    return round(total / weight_sum, 2)


def compute_all_factors(stock: Any, event: Dict[str, Any]) -> Dict[str, float]:
    """计算全部四因子 + 事件逻辑因子 + 综合得分。任一因子失败返回 0, 不影响其他。"""
    factors: Dict[str, float] = {}
    for name, fn in (
        ("event", calc_event_factor),
        ("value", calc_value_factor),
        ("growth", calc_growth_factor),
        ("market", calc_market_factor),
    ):
        try:
            factors[name] = fn(stock, event) if name == "event" else fn(stock)
        except Exception as e:  # noqa: BLE001
            logger.warning("因子[%s]计算失败: %s", name, str(e)[:100])
            factors[name] = 0.0

    # 事件逻辑因子 (B3)
    try:
        event_logic = calc_event_logic_composite(event, stock)
        factors.update(event_logic)
    except Exception as e:  # noqa: BLE001
        logger.warning("事件逻辑因子计算失败: %s", str(e)[:100])
        factors["event_strength"] = 0.0
        factors["chain_position"] = 0.0
        factors["logic_certainty"] = 0.0
        factors["event_logic_composite"] = 0.0

    factors["composite"] = calc_composite_score(factors)
    return factors


def compute_all_factors_batch(stocks: list, event: Dict[str, Any]) -> list:
    """批量计算全部因子。

    对一组股票逐个执行 compute_all_factors, 单只失败返回全 0 不影响其余。
    返回: [{"stock": StockProfile, "factors": {...}}, ...]
    """
    results = []
    for stock in stocks:
        try:
            factors = compute_all_factors(stock, event)
        except Exception as e:  # noqa: BLE001
            logger.warning("因子计算失败 %s: %s", getattr(stock, "code", "?"), str(e)[:100])
            factors = {"event": 0, "value": 0, "growth": 0, "market": 0, "composite": 0}
        results.append({"stock": stock, "factors": factors})
    return results


# ---- 技术指标 ----

def compute_technical_factors(code: str, closes: list = None) -> dict[str, float] | None:
    """仅使用真实收盘价计算技术指标；数据或依赖不足时返回 ``None``。"""
    try:
        import pandas_ta as ta
        import pandas as pd
    except ImportError:
        return None

    if not closes or len(closes) < 20:
        return None

    try:
        df = pd.DataFrame({"close": closes})

        # Trend: SMA crossover
        df["sma20"] = ta.sma(df["close"], length=20)
        df["sma50"] = ta.sma(df["close"], length=50) if len(closes) >= 50 else df["sma20"]
        trend_score = 50 + 25 * (1 if df["sma20"].iloc[-1] > df["sma50"].iloc[-1] else -1)

        # Momentum: RSI
        rsi = ta.rsi(df["close"], length=14)
        rsi_val = float(rsi.iloc[-1]) if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50
        momentum_score = rsi_val

        # Volume: OBV trend
        if "volume" in df.columns:
            df["obv"] = ta.obv(df["close"], df["volume"])
            obv_score = 50 + 25 * (1 if df["obv"].iloc[-1] > df["obv"].iloc[-5] else -1)
        else:
            obv_score = 50

        # Volatility: Bollinger Bands width
        bb = ta.bbands(df["close"], length=20)
        if bb is not None and not bb.empty:
            bb_col = [c for c in bb.columns if "BBB" in c.upper() or "BW" in c.upper()]
            if bb_col:
                bb_width = float(bb[bb_col[0]].iloc[-1])
                vol_score = min(100, max(0, 50 + (bb_width - 2) * 25))
            else:
                vol_score = 50
        else:
            vol_score = 50

        return {
            "trend": round(min(100, max(0, trend_score)), 1),
            "momentum": round(min(100, max(0, momentum_score)), 1),
            "volume": round(min(100, max(0, obv_score)), 1),
            "volatility": round(min(100, max(0, vol_score)), 1),
            "composite": round(min(100, max(0, (trend_score + momentum_score + obv_score + vol_score) / 4)), 1),
        }
    except Exception:
        return None
