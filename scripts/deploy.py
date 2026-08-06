"""一键部署脚本 (Windows 兼容, 跨平台)。

用法: python scripts/deploy.py

步骤: 检查环境 -> 安装依赖 -> 配置 .env -> 生成离线包 -> 生成演示数据
      -> 运行测试 -> 启动 UI
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def step(title: str) -> None:
    print(f"\n{'=' * 50}\n🚀 {title}\n{'=' * 50}")


def run(cmd: list) -> bool:
    """运行命令, 返回是否成功。"""
    print(f"  > {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"  ❌ 失败: {r.stderr[-500:] if r.stderr else '无错误输出'}")
            return False
        return True
    except FileNotFoundError as e:
        print(f"  ❌ 命令不存在: {e}")
        return False


def main() -> None:
    step("1/7 检查 Python 环境")
    if not run([sys.executable, "--version"]):
        sys.exit(1)

    step("2/7 安装依赖")
    if not run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"]):
        sys.exit(1)

    step("3/7 配置 .env")
    env_file = ROOT / ".env"
    if not env_file.exists():
        (ROOT / ".env.example").rename(env_file) if (ROOT / ".env.example").exists() else None
        print("  ⚠️ 已从 .env.example 创建 .env, 请编辑填入 ASCEND_API_KEY")
    else:
        print("  ✅ .env 已存在")

    step("4/7 生成离线包")
    if not run([sys.executable, "scripts/gen_offline_packs.py"]):
        print("  ⚠️ 离线包生成失败 (网络受限时跳过, 已存在的离线包仍可用)")

    step("5/7 生成演示数据")
    run([sys.executable, "scripts/demo_prep.py", "--no-market", "--max-stocks", "12"])

    step("6/7 运行测试")
    if not run([sys.executable, "-m", "pytest", "tests/", "-q"]):
        print("  ⚠️ 部分测试失败, 请检查")

    step("7/7 启动 UI")
    print("\n启动命令: streamlit run ui/app.py")
    print("访问: http://localhost:8501\n")

    # 交互式启动
    ans = input("是否现在启动 UI? (y/N): ").strip().lower()
    if ans in ("y", "yes"):
        run([sys.executable, "-m", "streamlit", "run", "ui/app.py", "--server.port", "8501"])


if __name__ == "__main__":
    main()
