"""自动恢复与告警: 组件失败自动尝试恢复, 连续失败告警。

Windows 兼容: 无信号依赖, 纯逻辑重试。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

from src.health_check import HealthChecker  # noqa: E402


class AutoRecovery:
    """自动恢复系统。"""

    def __init__(self, health_checker: Optional[HealthChecker] = None) -> None:
        self.health = health_checker or HealthChecker()
        self.failure_count: Dict[str, int] = {}
        self.alert_threshold = 3
        self.recovery_actions: Dict[str, Callable] = {
            "data_source": self._recover_data_source,
            "cache": self._recover_cache,
        }

    def check_and_recover(self) -> Dict[str, int]:
        """检查所有组件, 尝试恢复失败的。返回恢复动作数。"""
        status = self.health.check_all()
        recovered = 0

        for component, detail in status["details"].items():
            comp_status = detail.get("status")
            if comp_status in ("failed", "error"):
                self.failure_count[component] = self.failure_count.get(component, 0) + 1
                if component in self.recovery_actions:
                    logger.warning("尝试恢复 %s (失败%d次)...", component, self.failure_count[component])
                    ok = self.recovery_actions[component]()
                    if ok:
                        logger.info(" %s 恢复成功", component)
                        self.failure_count[component] = 0
                        recovered += 1
                    elif self.failure_count[component] >= self.alert_threshold:
                        self._send_alert(component, detail)
            elif comp_status == "ok":
                # 恢复正常则清零
                self.failure_count[component] = 0

        return {"recovered": recovered, "failures": dict(self.failure_count)}

    # ============ 恢复动作 ============

    def _recover_data_source(self) -> bool:
        """恢复数据源: 重置 socket 超时 + 重建缓存。"""
        try:
            import socket
            socket.setdefaulttimeout(5)
            from src.cache_manager import CacheManager
            cm = CacheManager()
            cm.clear()
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("数据源恢复失败: %s", str(e)[:80])
            return False

    def _recover_cache(self) -> bool:
        """恢复缓存: 确保目录与 demo_state 存在。"""
        try:
            from pathlib import Path
            root = Path(__file__).resolve().parent.parent
            (root / "data").mkdir(parents=True, exist_ok=True)
            demo = root / "data" / "demo_state.json"
            if not demo.exists():
                # 重建最小 demo_state (空模板)
                import json
                with open(demo, "w", encoding="utf-8") as f:
                    json.dump({"version": 1, "topics": {}}, f, ensure_ascii=False)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("缓存恢复失败: %s", str(e)[:80])
            return False

    def _send_alert(self, component: str, detail: dict) -> None:
        """发送告警 (当前: 日志告警, 预留邮件/企微)。"""
        message = (
            f"️ 系统告警 | 组件: {component} | 状态: {detail.get('status')} "
            f"| 消息: {detail.get('message')} | 时间: {datetime.now().strftime('%H:%M:%S')}"
        )
        logger.error(message)
