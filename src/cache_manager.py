"""三级缓存: 内存 -> SQLite -> 离线包。

- 内存缓存: 进程内, TTL 内直接命中
- SQLite 缓存: 持久化, 字段级 TTL
- 离线包: 保底数据源 (概念成分股)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from config import CACHE_TTL

logger = logging.getLogger(__name__)

CACHE_DB = Path(__file__).resolve().parent.parent / "data" / "cache.sqlite"


class CacheManager:
    """简单三级缓存。线程安全(写操作串行化)。"""

    def __init__(self, db_path: Path = CACHE_DB) -> None:
        self.db_path = db_path
        self._mem: Dict[str, tuple[float, Any]] = {}
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self) -> None:
        try:
            con = self._connect()
            con.execute(
                "CREATE TABLE IF NOT EXISTS cache ("
                "  key TEXT PRIMARY KEY,"
                "  value TEXT,"
                "  updated_at REAL)"
            )
            con.commit()
            con.close()
        except sqlite3.Error as e:
            logger.warning("SQLite 缓存初始化失败: %s", str(e)[:100])

    def get(self, key: str, ttl: float = CACHE_TTL) -> Optional[Any]:
        """读取缓存。内存优先, 其次 SQLite。过期/缺失返回 None。"""
        now = time.time()
        # 1. 内存
        if key in self._mem:
            ts, val = self._mem[key]
            if now - ts <= ttl * 60:
                return val
            del self._mem[key]
        # 2. SQLite
        try:
            con = self._connect()
            row = con.execute("SELECT value, updated_at FROM cache WHERE key=?", (key,)).fetchone()
            con.close()
            if row and now - row[1] <= ttl * 60:
                val = json.loads(row[0])
                self._mem[key] = (now, val)
                return val
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.warning("SQLite 读取失败 %s: %s", key, str(e)[:80])
        return None

    def set(self, key: str, value: Any) -> None:
        """写入缓存 (内存 + SQLite)。"""
        self._mem[key] = (time.time(), value)
        try:
            con = self._connect()
            con.execute(
                "INSERT OR REPLACE INTO cache (key, value, updated_at) VALUES (?,?,?)",
                (key, json.dumps(value, ensure_ascii=False), time.time()),
            )
            con.commit()
            con.close()
        except sqlite3.Error as e:
            logger.warning("SQLite 写入失败 %s: %s", key, str(e)[:80])

    def clear(self, prefix: str = "") -> None:
        """清除缓存。prefix 为空则全清。"""
        self._mem.clear()
        try:
            con = self._connect()
            if prefix:
                con.execute("DELETE FROM cache WHERE key LIKE ?", (f"{prefix}%",))
            else:
                con.execute("DELETE FROM cache")
            con.commit()
            con.close()
        except sqlite3.Error as e:
            logger.warning("SQLite 清除失败: %s", str(e)[:80])
