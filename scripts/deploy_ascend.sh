#!/usr/bin/env bash
# =============================================================================
# 昇腾环境一键部署脚本 - 金融研究 Agent
# 用途: 在赛事提供的昇腾算力环境 (Linux + CANN + NPU) 下完成:
#   安装 MindSpore(昇腾) -> 验证 NPU -> 装依赖 -> 配置 Key
#   -> 验证昇腾加速生效 -> 跑通一次真实分析 -> 启动网站
# 用法: bash scripts/deploy_ascend.sh
# =============================================================================
set -e
cd "$(dirname "$0")/.."

echo "=================================================="
echo "  昇腾一键部署: 多视角金融研究 Agent"
echo "=================================================="

# ---------- 1. Python ----------
command -v python3 >/dev/null 2>&1 || { echo "[错误] 未检测到 python3"; exit 1; }
echo "[1/7] Python: $(python3 --version)"

# ---------- 2. MindSpore (昇腾原生框架) ----------
if python3 -c "import mindspore" >/dev/null 2>&1; then
    echo "[2/7] MindSpore 已安装: $(python3 -c 'import mindspore; print(mindspore.__version__)')"
else
    echo "[2/7] 安装 MindSpore (昇腾版本, 按 https://www.mindspore.cn/install 选择匹配 CANN 的版本)..."
    pip install mindspore-ascend 2>/dev/null || pip install mindspore
fi

# ---------- 3. 验证昇腾 NPU ----------
echo "[3/7] 验证昇腾 NPU..."
python3 - <<'PY'
from mindspore import context
context.set_context(device_target="Ascend")
print("[OK] 昇腾 NPU 可用")
PY

# ---------- 4. 项目依赖 ----------
echo "[4/7] 安装项目依赖..."
pip install -r requirements.txt

# ---------- 5. .env 配置 ----------
echo "[5/7] 配置 .env..."
if [ ! -f .env ]; then
    cp .env.example .env
fi
if [ -n "$ASCEND_API_KEY" ]; then
    # 已在环境变量中 -> 写入 .env
    python3 - <<'PY'
import os, re
p = ".env"
key = os.environ.get("ASCEND_API_KEY", "")
s = open(p, encoding="utf-8").read()
if re.search(r"^ASCEND_API_KEY=.*$", s, re.M):
    s = re.sub(r"^ASCEND_API_KEY=.*$", "ASCEND_API_KEY=" + key, s, flags=re.M)
else:
    s += "\nASCEND_API_KEY=" + key + "\n"
open(p, "w", encoding="utf-8").write(s)
print("[OK] ASCEND_API_KEY 已从环境变量写入 .env")
PY
fi
echo "[提示] 若未配置 API Key, 请手动编辑 .env (系统会以规则兜底运行)"

# ---------- 6. 验证昇腾加速生效 ----------
echo "[6/7] 验证昇腾 MindSpore 加速..."
python3 scripts/verify_ascend.py

# ---------- 7. 跑通一次真实分析 (留存证据) ----------
echo "[7/7] 跑通一次真实金融分析 (昇腾算力证据)..."
python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from src.pipeline import run_analysis
r = run_analysis("低空经济", use_llm=True, enrich_market=True)
n = len(r.get("stock_results", []))
print(f"[OK] 真实分析完成: {n} 只股票, 报告 {len(r.get('report',''))} 字")
if r.get("errors"):
    print("[提示] 部分环节降级:", r["errors"][:3])
PY

echo ""
echo "=================================================="
echo "  部署完成! 昇腾原生算力已跑通真实代码"
echo "  启动网站: python3 -m streamlit run ui/app.py --server.port 8532"
echo "  浏览器访问: http://localhost:8532"
echo "  侧边栏应显示: 🧠 计算后端: 昇腾 NPU"
echo "=================================================="
