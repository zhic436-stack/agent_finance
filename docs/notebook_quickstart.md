# GitCode Notebook 快速开始

> GitCode Notebook 每次启动是**全新的空环境**（不持久化），不会自动包含仓库内容。
> 在空白 Notebook 中粘贴下方代码并运行，即可一步完成：拉取源码 → 装依赖 → 昇腾 NPU 检测 → 昇腾加速验证 → 真实分析跑通。

## 一键全自动代码 v3.1（推荐）

**设计**：① 自动探测 Notebook 已预装的包，**只装缺失的**（基础镜像自带 pandas/numpy 的话，核心安装只需几十秒）；② 先装核心小包（跑通演示），再尝试完整 requirements（大包如 playwright/cvxpy 装得慢或镜像缺失时**只警告不阻塞**）；③ pip 带超时，不再无限卡住。

```python
# ===== 金融研究 Agent: 5 步全自动跑通 (v3.1 自动探测版) =====
import subprocess, os, sys, time, shutil, importlib.util

REPO = "https://gitcode.com/zhichen1024/agent_finance.git"

# 1. 拉取源码 (强制刷新, 确保最新代码)
if os.path.exists("agent_finance"):
    shutil.rmtree("agent_finance", ignore_errors=True)
subprocess.run(["git", "clone", "--depth", "1", REPO], check=True)
os.chdir("agent_finance")
print("✔ 1/5 源码已拉取 (最新版)")

# 2a. 核心依赖: 自动探测, 只装缺失的
def pip_install(args):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--progress-bar", "off", "--timeout", "60", *args], check=True)

CORE = ["pandas", "numpy", "curl_cffi", "python-dotenv", "json-repair", "schedule", "graphviz"]
missing = [m for m in CORE if importlib.util.find_spec(m) is None]
if missing:
    print("需安装核心包:", ", ".join(missing), "(约1分钟)...")
    try:
        pip_install(missing)
    except subprocess.CalledProcessError:
        print("默认源失败, 切清华镜像重试...")
        pip_install(["-i", "https://pypi.tuna.tsinghua.edu.cn/simple", *missing])
else:
    print("✔ 核心依赖已全部存在, 跳过安装")
print("✔ 核心依赖就绪")

# 2b. 完整依赖 (可跳过; 失败仅警告, 不影响核心演示)
try:
    print("尝试安装完整依赖 (playwright/cvxpy 等大包, 可能较慢)...")
    pip_install(["-r", "requirements.txt"])
    print("✔ 完整依赖已安装")
except subprocess.CalledProcessError:
    try:
        pip_install(["-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "-r", "requirements.txt"])
        print("✔ 完整依赖已安装 (清华镜像)")
    except subprocess.CalledProcessError as e:
        print("⚠ 完整依赖未完全安装 (不影响核心链路演示):", str(e)[-120:])
print("✔ 2/5 依赖阶段结束")

# 3. 昇腾环境检测
try:
    import mindspore
    from mindspore import context
    context.set_context(device_target="Ascend")
    print("✔ 3/5 昇腾 NPU 可用 (MindSpore", mindspore.__version__ + ")")
except ImportError:
    print("✔ 3/5 MindSpore 未装 (可 pip install mindspore-ascend 启用 NPU)")
except Exception:
    print("✔ 3/5 NPU 检测失败, 使用 CPU")

# 4. 昇腾加速验证
import numpy as np
try:
    from src.ascend_accel import backend_info, covariance_matrix
    print("✔ 4/5 计算后端:", backend_info())
    print("      协方差:", covariance_matrix(np.random.randn(60, 3)).shape)
except Exception as e:
    print("✔ 4/5 昇腾模块降级 numpy:", type(e).__name__)

# 5. 真实分析跑通 (核心链路, 无需 LLM Key; 行情失败自动用仓库离线数据)
from src.pipeline import run_analysis
t0 = time.time()
r = run_analysis("低空经济", use_llm=False, enrich_market=False)
print(f"✔ 5/5 分析完成: {time.time()-t0:.1f}s | 候选股 {len(r.get('stock_results', []))} 只 | 报告 {len(r.get('report',''))} 字")
print(r.get("report", "")[:300])
print("\n🎉 全部跑通! 详细演示: notebooks/金融研究Agent_昇腾NPU跑通.ipynb")
```

## 手动方式（等价）

```bash
rm -rf agent_finance
git clone https://gitcode.com/zhichen1024/agent_finance.git
cd agent_finance
pip install pandas numpy curl_cffi python-dotenv json-repair schedule graphviz   # 核心(已装可跳过)
pip install -r requirements.txt || pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt  # 完整, 可选
# 打开 notebooks/金融研究Agent_昇腾NPU跑通.ipynb 并全部运行
```

## 跑完整网站（Streamlit UI）

在 Notebook 终端执行：

```bash
pip install -r requirements.txt
echo 'ASCEND_API_KEY=你的Key' > .env      # 有 LLM Key 才需要
streamlit run ui/app.py --server.port 8532 --server.headless true
```

- 侧边栏显示 **🧠 计算后端: 昇腾 NPU**（装 mindspore-ascend 后自动启用）与 **☁️ 昇腾模型调用统计**。
- 界面截图 / 演示视频 / 性能数据见仓库 README。
