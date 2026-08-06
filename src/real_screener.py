# -*- coding: utf-8 -*-
"""Real-time stock screening using akshare concept boards.
Replaces demo_state.json static screening with live market data.
If akshare is unavailable, falls back to offline cache.
"""
from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache for concept stock data (avoid repeated API calls)
_CONCEPT_CACHE: Dict[str, List[Dict]] = {}
_CACHE_TTL = 600  # 10 minutes


def screen_realtime_stocks(
    topic: str,
    event: Optional[Dict[str, Any]] = None,
    max_candidates: int = 30,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Screen stocks in real-time using akshare concept board API.

    1. Map topic to concept name
    2. Query concept constituent stocks
    3. Fetch market data for each stock
    4. Return stock profiles with real market data

    Falls back to static concept mapping if akshare is unavailable.
    Returns list of {"code": str, "name": str, "price": float, "pct_chg": float}.
    """
    try:
        import akshare as ak

        # Map topic to concept
        concept_name = _topic_to_concept(topic)
        if not concept_name:
            # Try benefited industries from event
            if event:
                industries = event.get("benefited_industries", [])
                concept_name = industries[0] if industries else topic
            else:
                concept_name = topic

        # Check cache
        cache_key = f"{concept_name}_{int(time.time() // _CACHE_TTL)}"
        if use_cache and cache_key in _CONCEPT_CACHE:
            return _CONCEPT_CACHE[cache_key][:max_candidates]

        # Query concept stocks
        try:
            df = ak.stock_board_concept_cons_em(symbol=concept_name)
        except Exception:
            # Try with "概念" suffix
            try:
                df = ak.stock_board_concept_cons_em(symbol=f"{concept_name}概念")
            except Exception:
                logger.warning("Concept query failed for: %s", concept_name)
                return _static_fallback(topic, max_candidates)

        if df is None or len(df) == 0:
            logger.warning("No stocks found for concept: %s", concept_name)
            return _static_fallback(topic, max_candidates)

        # Extract stock data
        stocks = []
        for _, row in df.iterrows():
            try:
                code = str(row.get("代码", row.get("code", "")))
                name = str(row.get("名称", row.get("name", "")))
                if not code:
                    continue
                stocks.append({
                    "code": code,
                    "name": name,
                    "price": 0.0,
                    "pct_chg": 0.0,
                })
            except Exception:
                continue

        # Fetch real-time market data
        stocks = _enrich_market_data(stocks)

        # Sort by market cap or turnover
        stocks.sort(key=lambda s: abs(float(s.get("pct_chg", 0))), reverse=True)
        result = stocks[:max_candidates]

        # Update cache
        _CONCEPT_CACHE[cache_key] = result
        return result

    except ImportError:
        logger.info("akshare not available, using static fallback")
        return _static_fallback(topic, max_candidates)
    except Exception as e:
        logger.warning("Real-time screening failed: %s", str(e)[:100])
        return _static_fallback(topic, max_candidates)


def _topic_to_concept(topic: str) -> str:
    """Map free-text topic to Eastmoney concept name."""
    concept_map = {
        "低空经济": "低空经济",
        "AI算力": "算力概念",
        "人工智能": "人工智能",
        "机器人": "机器人概念",
        "新能源": "新能源",
        "新能源汽车": "新能源车",
        "半导体": "半导体",
        "芯片": "半导体",
        "光伏": "光伏概念",
        "军工": "军工",
        "消费电子": "消费电子",
        "量子计算": "量子通信",
        "数据要素": "数据要素",
        "自动驾驶": "无人驾驶",
        "固态电池": "固态电池",
        "人形机器人": "机器人概念",
    }
    for key, val in concept_map.items():
        if key in topic:
            return val
    return topic  # Return as-is if no mapping


def _enrich_market_data(stocks: List[Dict]) -> List[Dict]:
    """Add real-time market data from akshare spot."""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            return stocks

        code_set = {s["code"] for s in stocks}
        market = {}
        for _, row in df.iterrows():
            code = str(row.get("代码", row.get("code", "")))
            if code in code_set:
                market[code] = {
                    "price": float(row.get("最新价", row.get("price", 0)) or 0),
                    "pct_chg": float(row.get("涨跌幅", row.get("pct_chg", 0)) or 0),
                    "volume": float(row.get("成交量", row.get("volume", 0)) or 0),
                    "turnover": float(row.get("成交额", row.get("amount", 0)) or 0),
                    "pe": float(row.get("市盈率-动态", row.get("pe", 0)) or 0),
                }
                code_set.discard(code)

        for s in stocks:
            md = market.get(s["code"], {})
            s["price"] = md.get("price", 0.0)
            s["pct_chg"] = md.get("pct_chg", 0.0)
            s["volume"] = md.get("volume", 0.0)
            s["turnover"] = md.get("turnover", 0.0)
            s["pe"] = md.get("pe", 0.0)
    except Exception as e:
        logger.debug("Market enrichment skipped: %s", str(e)[:80])
    return stocks


def _static_fallback(topic: str, max_candidates: int) -> List[Dict]:
    """Static concept-stock mapping when akshare is unavailable."""
    static_map = {
        "低空经济": ["300900", "300719", "002389", "688070", "000547"],
        "AI算力": ["688256", "688041", "300474", "002230", "603019"],
        "机器人": ["300124", "002747", "688017", "603728", "002527"],
        "新能源": ["300750", "002594", "601012", "688599", "600438"],
        "半导体": ["688981", "002371", "688012", "300782", "603986"],
    }

    # Find matching topic
    codes = []
    for key, vals in static_map.items():
        if key in topic:
            codes = vals
            break
    if not codes:
        codes = static_map.get("AI算力", [])

    # Basic stock info from known data
    known_stocks = {
        "300900": "广联航空", "300719": "安达维尔", "002389": "航天彩虹",
        "688070": "纵横股份", "000547": "航天发展", "688256": "寒武纪",
        "688041": "海光信息", "300474": "景嘉微", "002230": "科大讯飞",
        "603019": "中科曙光", "300124": "汇川技术", "002747": "埃斯顿",
        "688017": "绿的谐波", "603728": "鸣志电器", "002527": "新时达",
        "300750": "宁德时代", "002594": "比亚迪", "601012": "隆基绿能",
        "688599": "天合光能", "600438": "通威股份", "688981": "中芯国际",
        "002371": "北方华创", "688012": "中微公司", "300782": "卓胜微",
        "603986": "兆易创新",
    }
    return [
        {"code": c, "name": known_stocks.get(c, c), "price": 0.0, "pct_chg": 0.0}
        for c in codes[:max_candidates]
    ]
