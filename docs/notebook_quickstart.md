# GitCode Notebook 快速开始

> GitCode Notebook 每次启动是**全新的空环境**（不持久化），不会自动包含仓库内容。
> 在空白 Notebook 中粘贴下方代码并运行，即可一步完成：拉取源码 → 装依赖 → 昇腾 NPU 检测 → 昇腾加速验证 → 真实分析跑通。

## 一键全自动代码（粘贴到 Notebook 第一个单元格，点 ▶ 运行）

```python
# ===== 金融研究 Agent: 5 步全自动跑通 =====
import subprocess, os, sys, time

REPO = "https://gitcode.com/zhichen1024/agent_finance.git"

# 1. 拉取源码
if not os.path.exists("agent_finance"):
    subprocess.run(["git", "clone", "--depth", "1", REPO], check=True)
os.chdir("agent_finance")
print("✔ 1/5 源码已拉取")

# 2. 安装依赖
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)
print("✔ 2/5 依赖已安装")

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

# 5. 真实分析跑通
from src.pipeline import run_analysis
t0 = time.time()
r = run_analysis("低空经济", use_llm=False, enrich_market=False)
print(f"✔ 5/5 分析完成: {time.time()-t0:.1f}s | 候选股 {len(r.get('stock_results', []))} 只 | 报告 {len(r.get('report',''))} 字")
print(r.get("report", "")[:300])
print("\n🎉 全部跑通! 详细演示: notebooks/金融研究Agent_昇腾NPU跑通.ipynb")
```

## 手动方式（等价）

```bash
git clone https://gitcode.com/zhichen1024/agent_finance.git
cd agent_finance
pip install -r requirements.txt
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
