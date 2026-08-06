#!/bin/bash
# 昇腾环境探测: 在 GitCode NPU Notebook 终端运行  bash scripts/detect_ascend.sh
echo "================= 昇腾环境探测 ================="
echo "--- [1] NPU 设备 (npu-smi) ---"
if command -v npu-smi >/dev/null 2>&1; then
    npu-smi info 2>/dev/null | head -25
else
    echo "npu-smi 不可用 (当前可能不是 NPU 资源!)"
fi
echo
echo "--- [2] CANN 安装目录 ---"
if [ -d /usr/local/Ascend ]; then
    ls /usr/local/Ascend
    if [ -f /usr/local/Ascend/ascend-toolkit/latest/version.cfg ]; then
        cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -3
    fi
else
    echo "无 /usr/local/Ascend (CANN 未装)"
fi
echo
echo "--- [3] Python 版本 ---"
python3 --version
echo
echo "--- [4] 已装的 AI 框架 ---"
python3 -c "import mindspore; print('mindspore', mindspore.__version__)" 2>/dev/null || echo "mindspore: 未装"
python3 -c "import torch; print('torch', torch.__version__); print('torch.npu 可用:', torch.npu.is_available() if hasattr(torch,'npu') else 'N/A')" 2>/dev/null || echo "torch: 未装"
python3 -c "import torch_npu; print('torch_npu: OK')" 2>/dev/null || echo "torch_npu: 未装"
echo
echo "--- [5] 昇腾相关环境变量 ---"
env | grep -iE "ascend|cann|npu|device" | head -10 || echo "(无)"
echo "================= 探测结束 ================="
