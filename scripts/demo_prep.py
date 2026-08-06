"""演示准备脚本: 预热离线包 + 预计算4个预置热点完整结果。

用法: python scripts/demo_prep.py [--with-llm] [--no-market] [--max-stocks N]
输出: data/demo_state.json (供 UI 快速加载, 演示时无需现场分析)

演示流程建议:
1. 赛前运行本脚本, 生成 demo_state.json
2. 现场打开 UI, 点击预置热点即加载缓存结果 (<3秒)
3. 若现场网络好, 也可现场发起实时分析展示 Agent 轨迹

财务演示数据: 生成 demo_state 时默认开启 DEMO_DATA_FALLBACK,
让价值/成长因子在真实财务缺失时用【演示数据】兜底, 保证四因子全亮。
⚠️ 演示数据仅用于黑客松展示, 不代表真实财务, UI 会标注。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 生成演示状态时开启财务演示数据兜底 (仅本次进程生效)
os.environ["DEMO_DATA_FALLBACK"] = "1"

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Windows GBK 控制台无法输出 emoji, 强制 UTF-8
if sys.stdout and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

TOPICS = ["低空经济", "AI算力", "机器人", "新能源"]
OUTPUT = _ROOT / "data" / "demo_state.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="预计算演示状态")
    parser.add_argument("--with-llm", action="store_true", help="报告走 LLM 润色 (需配置 ASCEND_API_KEY)")
    parser.add_argument("--no-market", action="store_true", help="不拉实时行情 (离线复现, 市场因子为0)")
    parser.add_argument("--max-stocks", type=int, default=12, help="每主题候选股上限 (控制行情拉取耗时, 默认12只)")
    parser.add_argument("--market-budget", type=float, default=90.0,
                        help="行情拉取总预算秒数, 超时自动降级离线 pct_chg (默认90s)")
    args = parser.parse_args()

    from src.pipeline import run_analysis

    # 行情预算控制: 每主题给一个时间片, 超时则本次主题不再等
    def topic_market_enabled(budget_left: float, n_stocks: int) -> bool:
        # 需要至少 预算 > n*0.5s (降频下限的粗略估计) 才值得拉
        return budget_left > n_stocks * 0.6

    demo_state: dict = {
        "version": 2,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "with_llm": args.with_llm,
        "enrich_market": not args.no_market,
        "max_stocks": args.max_stocks,
        "topics": {},
    }

    import time as _time
    budget = args.market_budget

    for topic in TOPICS:
        print(f"⏳ 分析 {topic} ...", flush=True)
        t0 = _time.time()
        # 行情是否启用: 预算充足才实时拉, 否则降级离线
        use_market = (not args.no_market) and topic_market_enabled(budget, args.max_stocks)
        if not use_market and not args.no_market:
            print(f"   💡 行情预算不足, {topic} 降级为离线 pct_chg", flush=True)

        result = run_analysis(
            topic,
            use_llm=args.with_llm,
            enrich_market=use_market,
            max_candidates=args.max_stocks,
        )
        elapsed = int((_time.time() - t0) * 1000)
        budget -= elapsed / 1000.0
        # 精简存储: 保留事件/产业链/概念/报告/耗时, 股票详情序列化
        demo_state["topics"][topic] = {
            "event": result["event"],
            "chain": result["chain"],
            "concepts": result["concepts"],
            "report": result["report"],
            "elapsed_ms": result["elapsed_ms"],
            "stock_results": [
                {
                    "code": r["stock"].code,
                    "name": r["stock"].name,
                    "factors": r["factors"],
                    "risk": r["risk"],
                }
                for r in result["stock_results"]
            ],
            "errors": result["errors"],
        }
        print(f"  ✅ {topic}: {len(result['stock_results'])} 只候选股, {elapsed}ms")

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(demo_state, f, ensure_ascii=False, indent=2)
    print(f"\n✅ demo_state.json 已生成: {OUTPUT}")
    print(f"   预置热点 {len(TOPICS)} 个, 现场点击加载即可 (<3秒)")


if __name__ == "__main__":
    main()
