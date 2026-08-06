#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitCode Notebook / 任意 Python 环境一键跑通金融研究 Agent 核心链路。

用法:
    python setup_notebook.py            # 核心链路 (1-2 分钟)
    python setup_notebook.py --full     # 额外安装完整依赖 (playwright/cvxpy 等)
"""
import importlib.util
import subprocess
import sys
import time

CORE = [
    "pandas", "numpy", "curl_cffi",
    "python-dotenv", "json-repair", "schedule", "graphviz",
]
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def pip(args):
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         "--progress-bar", "off", "--timeout", "60", *args],
        check=True,
    )


def step1_core():
    missing = [m for m in CORE if importlib.util.find_spec(m) is None]
    if not missing:
        print("[1/4] 核心依赖已存在 OK")
        return
    print(f"[1/4] 安装核心依赖: {', '.join(missing)} (约1分钟)...")
    try:
        pip(missing)
    except subprocess.CalledProcessError:
        print("  默认源失败, 切换清华镜像重试...")
        pip(["-i", MIRROR, *missing])
    print("[1/4] 核心依赖就绪 OK")


def step2_full():
    if "--full" not in sys.argv:
        print("[2/4] 跳过完整依赖 (需要时: python setup_notebook.py --full)")
        return
    print("[2/4] 安装完整依赖 (playwright/cvxpy 等大包, 可能较慢)...")
    for args in (["-r", "requirements.txt"], ["-i", MIRROR, "-r", "requirements.txt"]):
        try:
            pip(args)
            print("[2/4] 完整依赖已安装 OK")
            return
        except subprocess.CalledProcessError:
            continue
    print("[2/4] 完整依赖未完全安装 (不影响核心链路)")


def step3_ascend():
    print("[3/4] 昇腾环境检测...")
    try:
        import mindspore
        from mindspore import context
        context.set_context(device_target="Ascend")
        print(f"  OK 昇腾 NPU 可用 (MindSpore {mindspore.__version__})")
    except ImportError:
        print("  - MindSpore 未安装 (昇腾环境执行: pip install mindspore-ascend)")
    except Exception as e:  # noqa: BLE001
        print(f"  - NPU 检测失败, 使用 CPU: {type(e).__name__}")


def step4_analysis():
    print("[4/4] 运行真实金融分析 (低空经济, 离线规则模式)...")
    from src.pipeline import run_analysis
    t0 = time.time()
    r = run_analysis("低空经济", use_llm=False, enrich_market=False)
    dt = time.time() - t0
    n = len(r.get("stock_results", []))
    rep = r.get("report", "")
    print(f"  OK 完成: {dt:.1f}s | 候选股 {n} 只 | 报告 {len(rep)} 字")
    print("  报告节选:", rep[:180].replace("\n", " "))
    return n, len(rep)


def main():
    print("=" * 52)
    print("  金融研究 Agent 一键跑通 (事件驱动四因子投研)")
    print("  仓库: https://gitcode.com/zhichen1024/agent_finance")
    print("=" * 52)
    step1_core()
    step2_full()
    step3_ascend()
    step4_analysis()
    print("=" * 52)
    print(" 核心链路跑通! 完整网站:")
    print("   streamlit run ui/app.py --server.port 8532")
    print("   详细演示: notebooks/金融研究Agent_昇腾NPU跑通.ipynb")


if __name__ == "__main__":
    main()
