"""批量拉取真实财务数据 (冲刺包 Phase 3)。

从各话题离线包取 Top 股票, 用 akshare 拉真实 PE/PB/ROE,
存入 data/financial_cache.json (含数据日期)。

注: 部分股票可能拉取失败或数据滞后, 会标注 data_status:
  - "real": 真实数据
  - "demo": 拉取失败, 用演示数据兜底 (UI 会标注)
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

if sys.stdout and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = _ROOT / "data" / "financial_cache.json"


def collect_top_codes(per_topic: int = 12) -> list:
    """从各话题离线包收集股票代码 (去重)。"""
    from src.data_collector import load_offline_stocks
    from config import OFFLINE_TOPICS

    codes = []
    seen = set()
    for topic in OFFLINE_TOPICS:
        for s in load_offline_stocks(topic)[:per_topic]:
            if s.code not in seen:
                seen.add(s.code)
                codes.append((s.code, s.name, topic))
    return codes


def fetch_real(code: str) -> dict | None:
    """拉取真实 PE/PB (仅估值接口, 快)。ROE 接口滞后, 不拉。失败返回 None。"""
    try:
        import akshare as ak
        df = ak.stock_value_em(symbol=code)
        if df is None or df.empty:
            return None
        row = df.iloc[-1]
        pe = float(row.get("PE(TTM)") or 0) or None
        pb = float(row.get("市净率") or 0) or None
        return {
            "pe": pe, "pb": pb, "roe": None,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
            "data_status": "real",
        }
    except Exception as e:  # noqa: BLE001
        print(f"    ⚠️ {code} 拉取失败: {str(e)[:50]}")
        return None


def main(per_topic: int = 3) -> None:
    print(f"开始批量拉取真实财务数据 (每话题 {per_topic} 只)...")
    codes = collect_top_codes(per_topic)
    print(f"共收集 {len(codes)} 只股票 (跨 {len(set(c for _, _, c in codes))} 话题)")

    result = {"stocks": {}, "last_update": datetime.now().isoformat(timespec="seconds")}
    real = demo = 0
    for code, name, topic in codes:
        data = fetch_real(code)
        if data:
            data["name"] = name
            data["topic"] = topic
            result["stocks"][code] = data
            real += 1
        else:
            # 兜底: 演示数据 (标注)
            from src.financial_demo_data import generate_financial_demo_data
            demo_data = generate_financial_demo_data(code, name)
            result["stocks"][code] = {
                **demo_data,
                "name": name, "topic": topic,
                "data_date": datetime.now().strftime("%Y-%m-%d"),
                "data_status": "demo",
            }
            demo += 1
        time.sleep(0.3)

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n完成: 真实 {real} 只, 演示兜底 {demo} 只, 共 {len(result['stocks'])} 只")
    print(f"已保存: {OUT}")


if __name__ == "__main__":
    main()
