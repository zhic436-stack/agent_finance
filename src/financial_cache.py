"""财务数据缓存系统 - 避免重复拉取, 24小时内复用。

文件: data/financial_cache.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "financial_cache.json"
CACHE_TTL_SECONDS = 86400  # 24小时


class FinancialCache:
    """财务数据缓存: 按股票代码存取, 过期自动失效。"""

    def __init__(self, cache_file: Path = CACHE_FILE) -> None:
        self.cache_file = cache_file
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("财务缓存加载失败: %s", str(e)[:60])
        return {"stocks": {}, "last_update": None}

    def _save(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("财务缓存保存失败: %s", str(e)[:60])

    def get(self, code: str) -> Optional[dict]:
        """获取财务数据, 过期返回 None。"""
        stock = self.data["stocks"].get(code)
        if not stock:
            return None
        updated = stock.get("updated_at", "2000-01-01T00:00:00")
        try:
            update_time = datetime.fromisoformat(updated)
        except ValueError:
            return None
        if datetime.now() - update_time > timedelta(seconds=CACHE_TTL_SECONDS):
            return None
        return stock

    def set(self, code: str, data: dict) -> None:
        """存储财务数据 (合并入已有字段)。"""
        entry = dict(data)
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        existing = self.data["stocks"].get(code, {})
        existing.update(entry)
        self.data["stocks"][code] = existing
        self.data["last_update"] = datetime.now().isoformat(timespec="seconds")
        self._save()

    def get_or_fetch(self, code: str, fetcher, *args, **kwargs) -> Optional[dict]:
        """缓存优先, 未命中或过期则调用 fetcher 获取。"""
        cached = self.get(code)
        if cached:
            return cached
        try:
            data = fetcher(*args, **kwargs)
            if data:
                self.set(code, data)
            return data
        except Exception as e:  # noqa: BLE001
            logger.warning("财务数据拉取失败 %s: %s", code, str(e)[:80])
            return cached  # 过期也返回旧数据 (降级)

    def refresh_all(self, stock_list: list) -> int:
        """批量刷新财务数据。返回成功数。"""
        from src.data_collector import get_stock_financials

        ok = 0
        for code in stock_list:
            try:
                fin = get_stock_financials(code)
                if fin:
                    self.set(code, {
                        "pe": fin.pe, "pb": fin.pb, "roe": fin.roe,
                        "pe_percentile": fin.pe_percentile,
                        "pb_percentile": fin.pb_percentile,
                        "revenue_growth": fin.revenue_growth,
                        "profit_growth": fin.profit_growth,
                    })
                    ok += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("刷新财务 %s 失败: %s", code, str(e)[:60])
        return ok
