"""定时任务调度器: 每日数据更新 / 每周清理。

Windows 兼容: 用 schedule 库轮询 (线程后台运行)。
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import schedule
    _HAS_SCHEDULE = True
except ImportError:
    _HAS_SCHEDULE = False


class Scheduler:
    """定时任务调度器。"""

    def __init__(self) -> None:
        self.tasks: Dict[str, Callable] = {}
        self.running = False
        self._thread: Optional[threading.Thread] = None

    # ============ 默认任务 ============

    def daily_update(self) -> None:
        """每日数据更新任务 (收盘后刷新离线包/财务缓存)。"""
        logger.info("[%s] 开始每日数据更新", datetime.now().strftime("%Y-%m-%d %H:%M"))
        updated = 0
        try:
            from src.data_collector import load_offline_stocks
            from config import OFFLINE_TOPICS
            for topic in OFFLINE_TOPICS:
                n = len(load_offline_stocks(topic))
                updated += n
            logger.info("每日更新: 离线包 %d 个话题, %d 只股票", len(OFFLINE_TOPICS), updated)
        except Exception as e:  # noqa: BLE001
            logger.error("每日更新失败: %s", str(e)[:100])

    def weekly_cleanup(self) -> None:
        """每周清理任务 (清缓存/历史)。"""
        logger.info("[%s] 每周清理", datetime.now().strftime("%Y-%m-%d %H:%M"))
        try:
            from src.cache_manager import CacheManager
            cm = CacheManager()
            cm.clear()
            logger.info("缓存已清理")
        except Exception as e:  # noqa: BLE001
            logger.error("每周清理失败: %s", str(e)[:100])

    # ============ 注册与运行 ============

    def register_daily(self, time_str: str = "15:30", func: Optional[Callable] = None) -> None:
        """注册每日任务 (默认 15:30 收盘后)。"""
        if not _HAS_SCHEDULE:
            logger.warning("schedule 未安装, 跳过注册")
            return
        target = func or self.daily_update
        schedule.every().day.at(time_str).do(target)
        self.tasks[f"daily@{time_str}"] = target

    def register_weekly_cleanup(self) -> None:
        """注册每周清理 (周日 00:00)。"""
        if not _HAS_SCHEDULE:
            return
        schedule.every().sunday.at("00:00").do(self.weekly_cleanup)
        self.tasks["weekly_cleanup"] = self.weekly_cleanup

    def _run_loop(self) -> None:
        while self.running:
            try:
                schedule.run_pending()
            except Exception as e:  # noqa: BLE001
                logger.error("调度循环错误: %s", str(e)[:100])
            time.sleep(30)

    def start_background(self) -> Optional[threading.Thread]:
        """后台启动调度器。"""
        if not _HAS_SCHEDULE:
            logger.warning("schedule 未安装, 无法启动调度器")
            return None
        if self.running:
            return self._thread
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("调度器已后台启动")
        return self._thread

    def stop(self) -> None:
        self.running = False


# 全局单例
scheduler = Scheduler()
