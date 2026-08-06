"""多源数据融合测试 (A2): 新浪备源 + 新鲜度检查。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_sources import check_freshness, get_market_data_multi, get_sina_quote


def test_sina_quote_structure():
    """新浪行情返回结构化数据 (网络可用时)。"""
    q = get_sina_quote("000099")
    if q is None:
        pytest.skip("新浪接口不可用 (网络/风控)")
    assert q.get("name"), "缺名称"
    assert q.get("price", 0) > 0, "缺价格"
    assert q.get("prev_close", 0) > 0, "缺昨收"


def test_market_data_multi_returns():
    """多源获取总返回 (东财或新浪或缓存, 不崩溃)。"""
    md, source = get_market_data_multi("000099")
    assert md is not None
    assert source in ("东方财富", "新浪财经", "离线缓存")


def test_freshness_missing():
    """未拉取过 -> 不新鲜。"""
    r = check_freshness("不存在的key_xyz")
    assert r["fresh"] is False
    assert r["last_fetch"] is None


def test_multi_never_crashes():
    """任意代码/任意源都不崩溃。"""
    for code in ["000099", "600519", "999999", ""]:
        md, source = get_market_data_multi(code)
        assert md is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
