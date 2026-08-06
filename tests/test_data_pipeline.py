"""Phase 1: 数据管道加固测试 (统一适配器 + 数据质量 + 财务缓存)。"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_adapter import (  # noqa: E402
    filter_valid_stocks,
    get_field_safe_alias,
    validate_factor,
    validate_stock_data,
    with_retry,
)
from src.financial_cache import FinancialCache  # noqa: E402


# ============ with_retry ============

def test_with_retry_success():
    """正常函数带重试装饰后正常返回。"""
    calls = []

    @with_retry(max_retries=3, timeout=5)
    def good():
        calls.append(1)
        return {"data": "ok"}

    assert good() == {"data": "ok"}
    assert len(calls) == 1


def test_with_retry_recovers():
    """前2次失败, 第3次成功 -> 返回结果。"""
    calls = []

    @with_retry(max_retries=3, timeout=5, backoff=0.01)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("临时故障")
        return "recovered"

    assert flaky() == "recovered"
    assert len(calls) == 3


def test_with_retry_timeout():
    """超时 -> 重试 -> 最终 None (不抛异常)。"""
    calls = []

    @with_retry(max_retries=2, timeout=1, backoff=0.01)
    def slow():
        calls.append(1)
        time.sleep(5)
        return "late"

    assert slow() is None
    assert len(calls) == 2


def test_with_retry_empty_is_failure():
    """返回空 DataFrame 视为失败并重试。"""
    calls = []

    @with_retry(max_retries=2, timeout=5, backoff=0.01)
    def empty_df():
        import pandas as pd
        calls.append(1)
        return pd.DataFrame()

    assert empty_df() is None
    assert len(calls) == 2


# ============ 数据质量 ============

class _Stock:
    def __init__(self, code, name, price, pct_chg):
        self.code, self.name, self.price, self.pct_chg = code, name, price, pct_chg


def test_validate_stock_ok():
    assert validate_stock_data(_Stock("000099", "中信海直", 14.0, 3.5)) == []


def test_validate_stock_missing():
    issues = validate_stock_data(_Stock("", "测试", 14.0, 3.5))
    assert "缺少字段: code" in issues


def test_validate_stock_price():
    issues = validate_stock_data(_Stock("000099", "测试", -5, 3.5))
    assert any("价格" in i for i in issues)


def test_validate_factor():
    assert validate_factor("pe", 20.0)
    assert validate_factor("pe", None) is False
    assert validate_factor("pe", "abc") is False
    assert validate_factor("pe", 2_000_000) is False


def test_filter_valid_stocks():
    good = _Stock("000099", "中信海直", 14.0, 3.5)
    bad = _Stock("", "坏数据", -5, 99.0)
    valid = filter_valid_stocks([good, bad])
    assert valid == [good]


# ============ 财务缓存 ============

def test_financial_cache_roundtrip(tmp_path):
    cache = FinancialCache(tmp_path / "test_cache.json")
    cache.set("000099", {"pe": 20.5})
    assert cache.get("000099")["pe"] == 20.5


def test_financial_cache_expiry(tmp_path):
    import json
    cache = FinancialCache(tmp_path / "test_cache.json")
    cache.set("000099", {"pe": 20.5})
    # 手动改旧时间戳
    cache.data["stocks"]["000099"]["updated_at"] = "2000-01-01T00:00:00"
    assert cache.get("000099") is None


def test_financial_cache_get_or_fetch(tmp_path):
    cache = FinancialCache(tmp_path / "test_cache.json")
    fetched = {"pe": 30.0, "roe": 0.15}

    # 未缓存 -> fetch
    result = cache.get_or_fetch("000099", lambda: fetched)
    assert result["pe"] == 30.0
    # 已缓存 -> 不再 fetch
    calls = []

    def fake_fetch():
        calls.append(1)
        return {"pe": 999}

    result2 = cache.get_or_fetch("000099", fake_fetch)
    assert result2["pe"] == 30.0
    assert len(calls) == 0


def test_field_safe_alias():
    assert get_field_safe_alias({"PE(TTM)": 25}, ["pe", "PE(TTM)"]) == 25
    assert get_field_safe_alias({"pe": 25}, ["pe", "PE(TTM)"]) == 25
    assert get_field_safe_alias({"x": 1}, ["pe"], 0.0) == 0.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
