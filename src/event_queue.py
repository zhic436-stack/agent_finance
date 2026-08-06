"""事件队列系统: 异步任务处理 (线程池 + 结果缓存)。

支持: 提交任务 -> 后台执行 -> 按 ID 获取结果 (带超时)。
"""
from __future__ import annotations

import queue
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict


class EventQueue:
    """事件队列 - 线程池异步执行任务。"""

    def __init__(self, num_workers: int = 3) -> None:
        self.queue: "queue.Queue" = queue.Queue()
        self.results: Dict[str, Dict[str, Any]] = {}
        self.workers: list = []
        self.running = False
        self._lock = threading.Lock()
        self.num_workers = num_workers

    def submit(self, task_id: str, func: Callable, *args, **kwargs) -> str:
        """提交任务, 返回 task_id。"""
        self.queue.put({
            "id": task_id,
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "submitted_at": datetime.now().isoformat(),
        })
        return task_id

    def start(self) -> None:
        """启动工作线程。"""
        if self.running:
            return
        self.running = True
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"EventWorker-{i}", daemon=True)
            t.start()
            self.workers.append(t)

    def _worker_loop(self) -> None:
        while self.running:
            try:
                task = self.queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                result = task["func"](*task["args"], **task["kwargs"])
                with self._lock:
                    self.results[task["id"]] = {
                        "status": "completed",
                        "result": result,
                        "completed_at": datetime.now().isoformat(),
                    }
            except Exception as e:  # noqa: BLE001 - 任务异常不杀线程
                with self._lock:
                    self.results[task["id"]] = {
                        "status": "failed",
                        "error": str(e)[:200],
                        "completed_at": datetime.now().isoformat(),
                    }

    def get_result(self, task_id: str, timeout: int = 30) -> Dict[str, Any]:
        """获取任务结果 (带超时)。"""
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if task_id in self.results:
                    return self.results[task_id]
            time.sleep(0.3)
        return {"status": "timeout"}

    def stop(self) -> None:
        self.running = False
        for w in self.workers:
            w.join(timeout=3)


# 全局单例
event_queue = EventQueue(num_workers=3)
