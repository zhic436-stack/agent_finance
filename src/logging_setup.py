"""统一日志配置: 标准格式 + 按日轮转 + 保留30天。

格式: [2026-08-01 14:23:01] [INFO] [data_collector] 消息
日志文件: data/logs/app_YYYYMMDD.log (按日轮转, 保留30天)
"""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"


def setup_logging(level: int = logging.INFO) -> None:
    """初始化全局日志 (幂等)。"""
    if logging.getLogger("agent_finance").handlers:
        return  # 已初始化

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler: 按日轮转, 保留30天
    file_handler = TimedRotatingFileHandler(
        _LOG_DIR / "app.log", when="midnight", backupCount=30, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    # 控制台 handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)

    root = logging.getLogger("agent_finance")
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console)


def get_logger(name: str) -> logging.Logger:
    """获取带 agent_finance 前缀的 logger (避免与三方库混用)。"""
    setup_logging()
    return logging.getLogger(f"agent_finance.{name}")
