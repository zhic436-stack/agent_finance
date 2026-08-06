"""离线包加载单元测试 (不依赖网络)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collector import load_offline_stocks

TOPICS = ["低空经济", "AI算力", "机器人", "新能源"]


def test_all_offline_load():
    for topic in TOPICS:
        stocks = load_offline_stocks(topic)
        assert len(stocks) > 0, f"{topic} 离线包为空"
        for s in stocks[:5]:
            assert s.code, f"{topic} 存在空 code"
            assert s.name, f"{topic} 存在空 name"


def test_offline_stock_schema():
    stocks = load_offline_stocks("低空经济")
    s = stocks[0]
    assert hasattr(s, "code")
    assert hasattr(s, "name")
    assert hasattr(s, "price")
    assert hasattr(s, "pct_chg")


def test_unknown_topic_empty():
    assert load_offline_stocks("不存在的主题") == []


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
