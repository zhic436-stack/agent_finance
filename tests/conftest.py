"""pytest 配置: 排除脚本模式测试文件。

以下文件以 `python tests/xxx.py` 脚本模式运行 (需 UI 于指定端口),
不含 pytest 用例, 收集时排除避免 import playwright 污染 pytest 流。
"""
collect_ignore = [
    "test_3d_interaction.py",
    "test_aceternity.py",
    "test_user_journey.py",
    "record_demo.py",
]
