"""离线包生成工具: 按概念 code 拉取成分股并保存到 data/offline/。

用法: python scripts/gen_offline_packs.py
生成: data/offline/{topic}.json, 含版本号和时间戳。

话题 -> 东财概念名 (code 从 concept_list.json 解析)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Windows GBK 控制台
if sys.stdout and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from curl_cffi import requests as creq  # noqa: E402

# 话题 -> 东财概念名 (精确)
TOPIC_CONCEPT = {
    "低空经济": "低空经济",
    "AI算力": "算力概念",
    "机器人": "机器人概念",
    "新能源": "新能源",
    "半导体": "存储芯片",
    "人工智能": "AIGC概念",
    "新能源汽车": "新能源车",
    "光伏": "光伏概念",
    "军工": "军工",
    "消费电子": "消费电子概念",
}

DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
CONCEPT_LIST = _ROOT / "data" / "offline" / "concept_list.json"
OUTPUT_DIR = _ROOT / "data" / "offline"


def load_concept_codes() -> dict:
    """从 concept_list.json 加载 {概念名: BK code}。"""
    with open(CONCEPT_LIST, encoding="utf-8") as f:
        return json.load(f)


def get_board_stocks(bk_code: str, page_size: int = 200) -> list:
    """按 NEW_BOARD_CODE 拉取成分股 (datacenter-web, 含降频)。"""
    import random

    stocks = []
    page = 1
    while True:
        params = {
            "reportName": "RPT_F10_CORETHEME_BOARDTYPE",
            "columns": "SECURITY_CODE,SECURITY_NAME_ABBR",
            "quoteColumns": "f2~01~SECURITY_CODE~LATEST_PRICE,f3~01~SECURITY_CODE~PCT_CHANGE",
            "pageSize": page_size, "pageNumber": page,
            "sortTypes": -1, "sortColumns": "SECURITY_CODE",
            "source": "WEB", "client": "WEB",
            "filter": f'(NEW_BOARD_CODE="{bk_code}")',
        }
        try:
            r = creq.get(DATACENTER_URL, params=params, timeout=15, impersonate="chrome")
            j = r.json()
        except Exception as e:
            print(f"    失败: {str(e)[:60]}")
            break
        if not j.get("result") or not j["result"].get("data"):
            break
        for x in j["result"]["data"]:
            stocks.append({
                "code": str(x.get("SECURITY_CODE", "")),
                "name": str(x.get("SECURITY_NAME_ABBR", "") or ""),
                "price": x.get("LATEST_PRICE"),
                "pct_chg": x.get("PCT_CHANGE"),
            })
        if page >= j["result"].get("pages", 1):
            break
        page += 1
        time.sleep(0.8 + random.uniform(0, 0.4))
    return stocks


def main() -> None:
    concepts = load_concept_codes()
    print(f"概念库 {len(concepts)} 条")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    version = datetime.now().strftime("%Y%m%d%H%M")
    for topic, em_name in TOPIC_CONCEPT.items():
        bk_code = concepts.get(em_name, "")
        if not bk_code:
            print(f"⚠️ {topic}: 东财无「{em_name}」概念, 跳过")
            continue
        print(f"⏳ {topic} ({em_name}/{bk_code}) ...", flush=True)
        stocks = get_board_stocks(bk_code)
        valid = [s for s in stocks if s["code"] and s["name"]]
        if not valid:
            print(f"⚠️ {topic}: 成分股为空, 跳过")
            continue
        out = {
            "concept": topic,
            "em_concept": em_name,
            "code": bk_code,
            "version": version,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "source": "datacenter-web.eastmoney.com RPT_F10_CORETHEME_BOARDTYPE",
            "stocks": valid,
        }
        fname = OUTPUT_DIR / f"{_safe_name(topic)}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        size_kb = fname.stat().st_size / 1024
        print(f"  ✅ {topic}: {len(valid)} 只 ({size_kb:.0f}KB)")

    print(f"\n完成. 版本号 {version}")


def _safe_name(topic: str) -> str:
    mapping = {
        "AI算力": "ai_compute",
        "低空经济": "low_altitude_economy",
        "机器人": "robot",
        "新能源": "new_energy",
        "半导体": "semiconductor",
        "人工智能": "ai",
        "新能源汽车": "new_energy_vehicle",
        "光伏": "solar",
        "军工": "defense",
        "消费电子": "consumer_electronics",
    }
    return mapping.get(topic, topic)


if __name__ == "__main__":
    main()
