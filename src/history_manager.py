"""分析历史记录管理器。

每次分析自动保存到 data/history/, 支持最近 N 条查看与重新加载。
文件: data/history/{timestamp}_{topic}.json
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HISTORY_DIR = Path(__file__).resolve().parent.parent / "data" / "history"


def _safe_filename(topic: str) -> str:
    """主题转安全文件名。"""
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", topic)
    return cleaned[:40] or "未命名"


def _normalize_for_save(result: Dict[str, Any]) -> Dict[str, Any]:
    """将结果规范化为可 JSON 序列化的结构 (stock_results 抽离为 dict)。"""
    normalized = dict(result)
    if "stock_results" in normalized and normalized["stock_results"]:
        norm_stocks = []
        for r in normalized["stock_results"]:
            stock = r.get("stock")
            norm_stocks.append({
                "code": getattr(stock, "code", ""),
                "name": getattr(stock, "name", ""),
                "factors": r.get("factors", {}),
                "risk": r.get("risk", {}),
            })
        normalized["stock_results"] = norm_stocks
    return normalized


def _reconstruct_for_load(data: Dict[str, Any]) -> Dict[str, Any]:
    """从规范化数据重建结果 (stock_results 还原为含 stock/factors/risk 的结构)。"""
    result = dict(data)
    if "stock_results" in result and result["stock_results"]:
        from types import SimpleNamespace
        rebuilt = []
        for r in result["stock_results"]:
            rebuilt.append({
                "stock": SimpleNamespace(
                    code=r.get("code", ""),
                    name=r.get("name", ""),
                    price=0.0,
                    pct_chg=0.0,
                ),
                "factors": r.get("factors", {}),
                "risk": r.get("risk", {}),
            })
        result["stock_results"] = rebuilt
    return result


def save_history(result: Dict[str, Any], topic: str) -> Optional[str]:
    """保存一次分析结果到历史目录。返回文件路径, 失败返回 None。"""
    try:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{ts}_{_safe_filename(topic)}.json"
        path = HISTORY_DIR / fname
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_normalize_for_save(result), f, ensure_ascii=False, indent=2)
        return str(path)
    except (OSError, TypeError) as e:
        logger.warning("历史保存失败: %s", str(e)[:80])
        return None


def list_history(limit: int = 10) -> List[Dict[str, Any]]:
    """列出最近 N 条历史记录 (按时间倒序)。

    返回: [{"path": str, "topic": str, "time": str, "elapsed_ms": int}, ...]
    """
    if not HISTORY_DIR.exists():
        return []
    files = sorted(HISTORY_DIR.glob("*.json"), reverse=True)[:limit]
    records: List[Dict[str, Any]] = []
    for p in files:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            # 从文件名解析时间戳
            m = re.match(r"(\d{8})_(\d{6})_(.+)\.json", p.name)
            time_str = ""
            if m:
                try:
                    time_str = datetime.strptime(
                        f"{m.group(1)} {m.group(2)}", "%Y%m%d %H%M%S"
                    ).strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    time_str = p.name
            records.append({
                "path": str(p),
                "topic": data.get("topic", p.stem),
                "time": time_str,
                "elapsed_ms": data.get("elapsed_ms", 0),
            })
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("历史读取失败 %s: %s", p.name, str(e)[:60])
    return records


def load_history(path: str) -> Optional[Dict[str, Any]]:
    """加载一条历史记录 (重建 UI 可用的结构)。失败返回 None。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return _reconstruct_for_load(data)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("历史加载失败 %s: %s", path, str(e)[:80])
        return None
