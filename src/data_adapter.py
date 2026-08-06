"""统一数据适配器: 所有数据调用的统一入口。

包含: 超时控制(线程实现, Windows 兼容) + 重试机制 + 降级策略 + 字段适配。

Windows 兼容说明: 任务包中的 signal.SIGALRM 超时在 Windows 不存在,
这里用 concurrent.futures 线程 + future.result(timeout) 实现等价超时。
"""
from __future__ import annotations

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from functools import wraps
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)

# 全局线程池 (供超时执行)
_EXECUTOR = ThreadPoolExecutor(max_workers=4)


def with_retry(max_retries: int = 3, timeout: int = 10, backoff: float = 1.0):
    """带重试 + 线程超时 + 空值降级的装饰器 (Windows 兼容)。

    用法:
        @with_retry(max_retries=3, timeout=10)
        def fetch_concept_list():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error: Optional[Exception] = None
            for attempt in range(max_retries):
                try:
                    # 线程超时执行
                    future = _EXECUTOR.submit(func, *args, **kwargs)
                    result = future.result(timeout=timeout)

                    # 空值降级判断
                    if result is not None:
                        empty = False
                        if hasattr(result, "empty"):
                            empty = bool(result.empty)
                        if not empty:
                            return result
                        raise ValueError("返回数据为空")
                    raise ValueError("返回 None")

                except (FutTimeout, ValueError, Exception) as e:  # noqa: BLE001
                    last_error = e
                    wait = backoff * (2 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "尝试 %d/%d 失败: %s, %.1fs后重试", attempt + 1, max_retries, str(e)[:60], wait
                    )
                    time.sleep(wait)

            logger.error("所有重试失败 (%s): %s", func.__name__, str(last_error)[:100])
            return None
        return wrapper
    return decorator


def get_field_safe_alias(data: Any, candidates: List[str], default: Any = None) -> Any:
    """按候选字段名安全取值 (复用 data_collector.get_field_safe 的增强版)。

    支持 dict / 对象属性 / pd.Series。全部缺失返回 default。
    """
    if data is None:
        return default
    # dict / Series
    getter = getattr(data, "get", None)
    if getter is not None:
        for key in candidates:
            val = getter(key)
            if val is not None:
                return val
        return default
    # 对象属性
    for key in candidates:
        val = getattr(data, key, None)
        if val is not None:
            return val
    return default


# ============ 数据质量检查 ============


def validate_stock_data(stock: Any) -> List[str]:
    """检查股票数据完整性。返回问题列表 (空列表 = 通过)。"""
    issues: List[str] = []
    required = ["code", "name"]
    for field in required:
        val = getattr(stock, field, None)
        if not val:
            issues.append(f"缺少字段: {field}")

    price = getattr(stock, "price", None)
    if price is not None:
        try:
            if float(price) <= 0:
                issues.append(f"价格异常: {price}")
        except (TypeError, ValueError):
            issues.append(f"价格非数值: {price}")

    pct = getattr(stock, "pct_chg", None)
    if pct is not None:
        try:
            if abs(float(pct)) > 20.0:  # A股单日涨跌幅上限 ~10%
                issues.append(f"涨跌幅异常: {pct}")
        except (TypeError, ValueError):
            issues.append(f"涨跌幅非数值: {pct}")

    return issues


def validate_factor(factor_name: str, value: Any) -> bool:
    """检查因子值合理性。"""
    if value is None:
        return False
    if not isinstance(value, (int, float)):
        return False
    if value != value:  # NaN
        return False
    if abs(value) > 1_000_000:
        return False
    return True


def filter_valid_stocks(stocks: List[Any]) -> List[Any]:
    """过滤含问题的股票 (保留质量合格)。"""
    valid = []
    for s in stocks:
        issues = validate_stock_data(s)
        if not issues:
            valid.append(s)
        else:
            logger.debug("股票 %s 数据质量问题: %s", getattr(s, "code", "?"), issues)
    return valid
