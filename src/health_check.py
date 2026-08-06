"""系统健康检查: 全面监控系统状态。

检查项: 系统(CPU/内存) / 网络 / 数据源 / 昇腾API / 缓存 / 磁盘。
psutil 不可用时降级为标准库实现。
"""
from __future__ import annotations

import logging
import socket
from datetime import datetime
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


class HealthChecker:
    """系统健康检查器。"""

    def __init__(self) -> None:
        self.checks: Dict[str, Callable] = {
            "system": self._check_system,
            "network": self._check_network,
            "data_source": self._check_data_source,
            "ascend_api": self._check_ascend_api,
            "cache": self._check_cache,
            "offline_packs": self._check_offline_packs,
        }

    # ============ 单项检查 ============

    def _check_system(self) -> Dict[str, Any]:
        if _HAS_PSUTIL:
            return {
                "status": "ok",
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory_percent": psutil.virtual_memory().percent,
            }
        import os
        try:
            load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0
        except OSError:
            load1 = 0
        return {"status": "ok", "cpu_load": load1, "note": "psutil 未安装, 使用标准库"}

    def _check_network(self) -> Dict[str, Any]:
        try:
            socket.gethostbyname("api-ai.gitcode.com")
            return {"status": "ok", "message": "网络可达"}
        except socket.gaierror as e:
            return {"status": "failed", "message": f"DNS 解析失败: {e}"}
        except OSError as e:
            return {"status": "failed", "message": str(e)}

    def _check_data_source(self) -> Dict[str, Any]:
        try:
            from src.data_collector import load_offline_stocks
            n = len(load_offline_stocks("低空经济"))
            if n > 0:
                return {"status": "ok", "message": f"离线包可用 ({n}只低空经济股)"}
            return {"status": "degraded", "message": "离线包为空"}
        except Exception as e:  # noqa: BLE001
            return {"status": "failed", "message": str(e)[:80]}

    def _check_ascend_api(self) -> Dict[str, Any]:
        import config
        if not config.ASCEND_API_KEY:
            return {"status": "degraded", "message": "ASCEND_API_KEY 未配置, LLM 走规则兜底"}
        try:
            from src.ascend_monitor import monitor
            status = monitor.get_status()
            if status["total_calls"] > 0:
                return {"status": status["status"], "message": status["success_rate"], "detail": status}
            # 无调用记录: 做一次轻量探测
            from src.llm import chat_completion
            resp = chat_completion("你是助手", "ping", timeout=15, max_tokens=5)
            if resp:
                return {"status": "ok", "message": "API 正常"}
            return {"status": "degraded", "message": "API 探测无响应"}
        except Exception as e:  # noqa: BLE001
            return {"status": "failed", "message": str(e)[:80]}

    def _check_cache(self) -> Dict[str, Any]:
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        files = ["data/demo_state.json", "data/offline/low_altitude_economy.json"]
        exist = [f for f in files if (root / f).exists()]
        missing = [f for f in files if f not in exist]
        status = "ok" if not missing else ("degraded" if exist else "failed")
        return {"status": status, "present": exist, "missing": missing}

    def _check_offline_packs(self) -> Dict[str, Any]:
        from config import OFFLINE_TOPICS
        from src.data_collector import load_offline_stocks
        counts = {t: len(load_offline_stocks(t)) for t in OFFLINE_TOPICS}
        empty = [t for t, n in counts.items() if n == 0]
        return {
            "status": "ok" if not empty else "degraded",
            "topic_count": len(counts),
            "empty_topics": empty,
        }

    # ============ 汇总 ============

    def check_all(self) -> Dict[str, Any]:
        """执行所有检查, 返回总体状态。"""
        results: Dict[str, Any] = {}
        for name, check_func in self.checks.items():
            try:
                results[name] = check_func()
            except Exception as e:  # noqa: BLE001
                results[name] = {"status": "error", "message": str(e)[:80]}

        statuses = [r.get("status") for r in results.values()]
        if all(s == "ok" for s in statuses):
            overall = "healthy"
        elif any(s in ("failed", "error") for s in statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "overall_status": overall,
            "details": results,
        }
