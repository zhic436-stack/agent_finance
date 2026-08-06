#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""昇腾环境验证脚本: 打印昇腾技术栈状态, 确认 NPU 启用。

用法:
    python3 scripts/verify_ascend.py          # 昇腾环境验证 (非 Ascend 时退出码 1)
    python3 scripts/verify_ascend.py --info   # 仅打印状态, 不校验 (本机开发可用)
"""
import sys

sys.path.insert(0, ".")

from src.ascend_accel import backend_info  # noqa: E402


def main() -> int:
    info = backend_info()
    print("昇腾技术栈状态:")
    print(f"  框架     : {info['framework']}")
    print(f"  版本     : {info.get('mindspore_version') or '-'}")
    print(f"  设备     : {info['device']}")
    print(f"  昇腾 NPU : {'已启用' if info['ascend_npu'] else '未启用'}")
    print(f"  说明     : {info['note']}")

    if "--info" in sys.argv:
        return 0
    if not info["ascend_npu"]:
        print("\n[错误] 昇腾 NPU 未启用! 请确认已安装 mindspore-ascend 且 device_target 可设为 Ascend。")
        return 1
    print("\n[OK] 昇腾原生算力已启用 (device=Ascend), 协方差/归一化将由 MindSpore 在 NPU 上执行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
