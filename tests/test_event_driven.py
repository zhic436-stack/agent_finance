"""Phase 4: 事件队列 + 定时调度器测试。"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.event_queue import EventQueue  # noqa: E402
from src.scheduler import Scheduler  # noqa: E402


# ============ 事件队列 ============

def test_queue_completes_tasks():
    """3个并发任务全部完成, 无死锁。"""
    q = EventQueue(num_workers=3)
    q.start()

    def task(n):
        time.sleep(0.1)
        return n * 2

    ids = [q.submit(f"t{i}", task, i) for i in range(3)]
    for tid in ids:
        result = q.get_result(tid, timeout=5)
        assert result["status"] == "completed"
    q.stop()


def test_queue_handles_exception():
    """任务抛异常 -> status=failed, 不杀线程。"""
    q = EventQueue(num_workers=1)
    q.start()

    def boom():
        raise ValueError("测试异常")

    q.submit("bad", boom)
    result = q.get_result("bad", timeout=5)
    assert result["status"] == "failed"
    assert "测试异常" in result.get("error", "")
    q.stop()


def test_queue_timeout():
    """结果未就绪 -> timeout。"""
    q = EventQueue(num_workers=1)
    # 不 start, 任务不会执行 -> get 超时
    q.submit("never", lambda: 1)
    result = q.get_result("never", timeout=1)
    assert result["status"] == "timeout"


# ============ 调度器 ============

def test_scheduler_daily_update_runs():
    """daily_update 可执行且不崩溃。"""
    s = Scheduler()
    s.daily_update()  # 直接调用


def test_scheduler_weekly_cleanup_runs():
    """weekly_cleanup 可执行且不崩溃。"""
    s = Scheduler()
    s.weekly_cleanup()


def test_scheduler_register():
    """注册任务不崩溃 (schedule 缺失时优雅降级)。"""
    s = Scheduler()
    s.register_daily("15:30")
    s.register_weekly_cleanup()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
