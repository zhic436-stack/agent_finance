"""昇腾 API 监控: 记录调用状态/延迟/错误率, 提供状态报告。"""
from __future__ import annotations

import time
from typing import Dict


class AscendMonitor:
    """昇腾 API 调用监控 (线程安全 via GIL, 简单计数器)。"""

    def __init__(self) -> None:
        self.metrics = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "avg_latency": 0.0,
            "error_rates": {},
            "recent": [],  # 最近50次调用 {ts, ok, latency, model}
        }

    def record_call(self, success: bool, latency: float, model: str = "default") -> None:
        """记录一次调用。"""
        self.metrics["total_calls"] += 1
        if success:
            self.metrics["success_calls"] += 1
        else:
            self.metrics["failed_calls"] += 1
            self.metrics["error_rates"][model] = self.metrics["error_rates"].get(model, 0) + 1

        n = self.metrics["total_calls"]
        self.metrics["avg_latency"] = (self.metrics["avg_latency"] * (n - 1) + latency) / n

        # 最近调用环形记录
        self.metrics["recent"].append({"ts": time.time(), "ok": success, "latency": round(latency, 2), "model": model})
        if len(self.metrics["recent"]) > 50:
            self.metrics["recent"] = self.metrics["recent"][-50:]

    def get_status(self) -> Dict:
        """获取 API 状态报告。"""
        total = self.metrics["total_calls"]
        success_rate = self.metrics["success_calls"] / max(total, 1)
        return {
            "total_calls": total,
            "success_rate": f"{success_rate * 100:.1f}%",
            "avg_latency": f"{self.metrics['avg_latency']:.2f}s",
            "failed_calls": self.metrics["failed_calls"],
            "status": "healthy" if total > 0 and success_rate > 0.9 else ("degraded" if total > 0 else "idle"),
            "error_rates": self.metrics["error_rates"],
        }

    def reset(self) -> None:
        self.__init__()


# 全局单例
monitor = AscendMonitor()
