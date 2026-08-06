"""财务演示数据生成器。

️ 重要声明: 本模块生成的是【演示数据】(demo/simulated), 基于行业均值随机生成,
用于黑客松演示展示四因子框架的完整效果, 不代表任何真实上市公司的财务数据,
不构成任何投资建议。UI 必须标注"演示数据"。

设计:
- 用股票代码做种子, 保证同一股票每次生成一致 (可复现)
- 数值范围基于 A 股常见区间: PE 15-40, PB 1-8, ROE 2%-25%
- 演示数据仅在"实时财务数据缺失"时兜底, 绝不覆盖真实数据
"""
from __future__ import annotations

import hashlib
import logging
import random
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 演示数据范围 (A 股常见区间)
_PE_RANGE = (15.0, 40.0)
_PB_RANGE = (1.0, 8.0)
_ROE_RANGE = (0.02, 0.25)
_REV_GROWTH_RANGE = (-0.05, 0.40)
_PROFIT_GROWTH_RANGE = (-0.10, 0.50)

# 缓存: code -> 生成结果 (进程内, 保证可复现)
_CACHE: Dict[str, Dict[str, float]] = {}


def _seed_for(code: str) -> int:
    """由股票代码生成稳定种子 (可复现)。"""
    digest = hashlib.md5(code.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def generate_financial_demo_data(stock_code: str, stock_name: str = "") -> Dict[str, float]:
    """为演示股票生成合理的财务演示数据 (确定性, 同代码同结果)。

    注意: 这是演示数据, 仅用于黑客松展示, 不用于真实投资决策。

    返回:
        {
            "pe": float, "pb": float, "roe": float,
            "pe_percentile": float, "pb_percentile": float,
            "revenue_growth": float, "profit_growth": float,
            "is_demo": True,
        }
    """
    if stock_code in _CACHE:
        return _CACHE[stock_code]

    rng = random.Random(_seed_for(stock_code))

    pe = round(rng.uniform(*_PE_RANGE), 1)
    pb = round(rng.uniform(*_PB_RANGE), 2)
    roe = round(rng.uniform(*_ROE_RANGE), 4)
    rev_g = round(rng.uniform(*_REV_GROWTH_RANGE), 4)
    prof_g = round(rng.uniform(*_PROFIT_GROWTH_RANGE), 4)

    # PE 分位: PE 越高分位越高 (估值贵); PB 同理
    pe_pct = round(_map_to_percentile(pe, _PE_RANGE), 3)
    pb_pct = round(_map_to_percentile(pb, _PB_RANGE), 3)

    result = {
        "pe": pe,
        "pb": pb,
        "roe": roe,
        "pe_percentile": pe_pct,
        "pb_percentile": pb_pct,
        "revenue_growth": rev_g,
        "profit_growth": prof_g,
        "is_demo": True,
    }
    _CACHE[stock_code] = result
    return result


def _map_to_percentile(value: float, rng: tuple) -> float:
    """将值线性映射到 [0,1] 分位 (用于演示 PE/PB 分位)。"""
    lo, hi = rng
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def get_demo_financial_data(code: str, key: Optional[str] = None):
    """读取演示财务数据 (factor_engine 降级调用)。

    参数:
        code: 股票代码
        key: 指定字段, None 返回整个 dict

    返回: 字段值 / dict / None (未生成时 None)
    """
    data = _CACHE.get(code) or generate_financial_demo_data(code)
    if key is None:
        return data
    return data.get(key)


def demo_data_available(code: str) -> bool:
    """演示数据是否可生成 (总是 True, 用代码种子即可生成)。"""
    return bool(code)
