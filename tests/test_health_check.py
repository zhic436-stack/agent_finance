"""Phase 5: 健康检查与自动恢复测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auto_recovery import AutoRecovery  # noqa: E402
from src.health_check import HealthChecker  # noqa: E402


def test_check_all_structure():
    """健康检查返回完整结构。"""
    s = HealthChecker().check_all()
    assert "timestamp" in s
    assert s["overall_status"] in ("healthy", "degraded", "unhealthy")
    assert "details" in s
    for key in ("system", "network", "data_source", "ascend_api", "cache", "offline_packs"):
        assert key in s["details"]


def test_system_check():
    r = HealthChecker()._check_system()
    assert r["status"] == "ok"


def test_network_check():
    r = HealthChecker()._check_network()
    assert r["status"] in ("ok", "failed")  # 离线环境允许 failed


def test_cache_check():
    r = HealthChecker()._check_cache()
    assert r["status"] in ("ok", "degraded", "failed")
    assert "present" in r


def test_offline_packs_check():
    r = HealthChecker()._check_offline_packs()
    assert r["status"] in ("ok", "degraded")
    assert r["topic_count"] >= 10


def test_auto_recovery_runs():
    """自动恢复执行不崩溃。"""
    rec = AutoRecovery()
    result = rec.check_and_recover()
    assert "recovered" in result
    assert "failures" in result


def test_recover_cache():
    """缓存恢复动作返回 bool。"""
    rec = AutoRecovery()
    assert isinstance(rec._recover_cache(), bool)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
