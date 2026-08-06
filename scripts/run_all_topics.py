"""10 话题全量分析 + 性能基准 (冲刺包 Phase 4)。

运行: python scripts/run_all_topics.py
输出: docs/verification/phase4/all_topics_analysis.json + benchmark_results.txt
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if sys.stdout and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.pipeline import run_analysis  # noqa: E402


def main() -> None:
    topics = ["低空经济", "AI算力", "机器人", "新能源", "半导体",
              "人工智能", "新能源汽车", "光伏", "军工", "消费电子"]

    results = {}
    timing = []
    for topic in topics:
        print(f"正在分析: {topic}...", flush=True)
        t0 = time.time()
        try:
            r = run_analysis(topic, use_llm=False, max_candidates=10, enrich_market=False)
            elapsed = time.time() - t0
            timing.append(elapsed)
            results[topic] = {
                "event_type": r.get("event", {}).get("event_type", ""),
                "chain_count": len(r.get("chain", [])),
                "stock_count": len(r.get("stock_results", [])),
                "has_hypothesis": bool(r.get("hypothesis", {}).get("core_logic")),
                "report_len": len(r.get("report", "")),
                "elapsed_s": round(elapsed, 2),
                "trace_steps": len(r.get("trace", [])),
            }
            print(f"  ✅ {topic}: {len(r.get('stock_results', []))}只, {elapsed:.1f}s")
        except Exception as e:  # noqa: BLE001
            results[topic] = {"error": str(e)[:100]}
            print(f"  ❌ {topic}: {e}")

    # 汇总
    ok = [t for t, r in results.items() if "error" not in r]
    avg = sum(timing) / len(timing) if timing else 0
    summary = {
        "topic_count": len(topics),
        "success_count": len(ok),
        "avg_elapsed_s": round(avg, 2),
        "max_elapsed_s": round(max(timing), 2) if timing else 0,
        "topics": results,
    }

    out_dir = _ROOT / "docs" / "verification" / "phase4"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "all_topics_analysis.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(out_dir / "benchmark_results.txt", "w", encoding="utf-8") as f:
        f.write(f"10话题全量分析基准\n")
        f.write(f"成功率: {len(ok)}/{len(topics)}\n")
        f.write(f"平均耗时: {avg:.2f}s\n")
        f.write(f"最大耗时: {max(timing):.2f}s\n" if timing else "无")
    print(f"\n汇总: 成功 {len(ok)}/{len(topics)}, 平均 {avg:.2f}s")
    print(f"已保存: {out_dir}")


if __name__ == "__main__":
    main()
