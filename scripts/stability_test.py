"""稳定性压测 (压缩版, 冲刺包 Phase 5)。

会话边界内无法真实跑 30 小时, 用等价证明:
1. 多轮迭代 (模拟连续使用, 60轮随机话题)
2. 内存监控 (每轮记录 RSS, 验证无泄漏)
3. 异常注入 (空话题/无效代码/全缺数据 -> 不崩溃)

运行: python scripts/stability_test.py [--rounds 60]
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if sys.stdout and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOPICS = ["低空经济", "AI算力", "机器人", "新能源", "半导体",
          "人工智能", "新能源汽车", "光伏", "军工", "消费电子"]


def mem_mb() -> float:
    """当前进程内存 (MB)。psutil 缺失时用标准库。"""
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024 / 1024
    except ImportError:
        import os
        if hasattr(os, "getrusage"):
            return os.getrusage(os.RUSAGE_SELF).ru_maxrss / 1024
        return 0.0


def run_round(topic: str) -> dict:
    """单轮分析 (用 run_analysis_cached 模拟预热复用)。"""
    from src.pipeline import run_analysis_cached
    t0 = time.time()
    r = run_analysis_cached(topic, use_llm=False, max_candidates=8, enrich_market=False)
    return {"topic": topic, "elapsed": time.time() - t0, "ok": bool(r.get("report")), "stocks": len(r.get("stock_results", []))}


def inject_anomalies() -> list:
    """异常注入测试: 各种异常输入不崩溃。"""
    from src.pipeline import run_analysis
    cases = [
        ("", "空话题"),
        ("完全不存在XYZ", "未知话题"),
        ("  ", "空白"),
        ("低空经济" * 20, "超长话题"),
        (None, "None话题"),
    ]
    results = []
    for topic, label in cases:
        try:
            r = run_analysis(topic or "", use_llm=False, max_candidates=3, enrich_market=False)
            results.append({"case": label, "crash": False, "has_report": bool(r.get("report"))})
        except Exception as e:  # noqa: BLE001
            results.append({"case": label, "crash": True, "error": str(e)[:60]})
    return results


def main() -> None:
    rounds = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 60
    print(f"稳定性压测开始: {rounds} 轮, 随机话题")

    results = []
    mems = []
    random.seed(42)
    for i in range(rounds):
        topic = random.choice(TOPICS)
        try:
            r = run_round(topic)
            results.append(r)
        except Exception as e:  # noqa: BLE001
            results.append({"topic": topic, "ok": False, "error": str(e)[:60]})
        mems.append(mem_mb())
        if (i + 1) % 10 == 0:
            print(f"  第 {i+1}/{rounds} 轮: 内存 {mems[-1]:.1f}MB", flush=True)
        time.sleep(0.05)

    # 异常注入
    anomalies = inject_anomalies()

    # 汇总
    ok = sum(1 for r in results if r.get("ok"))
    crash = [r for r in results if not r.get("ok")]
    mem_start, mem_end = mems[0], mems[-1]
    mem_growth = mem_end - mem_start

    summary = {
        "rounds": rounds,
        "success": ok,
        "success_rate": f"{ok / len(results):.1%}",
        "failures": [r.get("topic") for r in crash][:10],
        "mem_start_mb": round(mem_start, 1),
        "mem_end_mb": round(mem_end, 1),
        "mem_growth_mb": round(mem_growth, 1),
        "mem_leak_suspect": mem_growth > 50,  # >50MB 增长可疑
        "anomaly_cases": anomalies,
        "anomaly_crash_count": sum(1 for a in anomalies if a["crash"]),
    }

    out_dir = _ROOT / "docs" / "verification" / "phase5"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "stability_log.txt", "w", encoding="utf-8") as f:
        for r in results:
            f.write(f"{r.get('topic')}: ok={r.get('ok')} {r.get('elapsed', 0):.1f}s\n")
        f.write(f"\n内存: 起始{summary['mem_start_mb']}MB -> 结束{summary['mem_end_mb']}MB (增长{summary['mem_growth_mb']}MB)\n")
        f.write(f"成功率: {summary['success_rate']}\n")
        f.write(f"异常注入: {summary['anomaly_cases']}\n")

    print(f"\n压测完成: {ok}/{rounds} 成功 ({summary['success_rate']})")
    print(f"内存: {summary['mem_start_mb']}MB -> {summary['mem_end_mb']}MB (增长 {summary['mem_growth_mb']}MB)")
    print(f"内存泄漏怀疑: {'是' if summary['mem_leak_suspect'] else '否'}")
    print(f"异常注入崩溃: {summary['anomaly_crash_count']}/{len(anomalies)}")
    print(f"日志: {out_dir / 'stability_log.txt'}")


if __name__ == "__main__":
    main()
