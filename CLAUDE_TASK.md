【桌面目录】~/Desktop/agent_finance
【当前问题汇总】经过人工验证，以下9个问题必须在本次交付中修复：

1. BUG: ui/app.py第20行硬编码了乱码主题"됴왕쒔셌"，导致demo永不自动加载。改为从demo_state.json动态读取第一个主题名。
2. BUG: 低空经济的chain为0，检查pipeline.py和event_analyzer.py的链推理逻辑。
3. MISSING: charts.py已经import了Kline但从未使用。在6_回测.py中添加K线图展示回测期间的价格走势。
4. MISSING: quantstats已安装(v0.0.81)但backtest_adapter.py没有任何调用。在回测页引入quantstats HTML报告。
5. MISSING: factor_engine.py的compute_technical_factors已写好但UI页从未调用。在2_多因子分析.py中添加技术指标section（RSI/MACD/布林带卡片+小图表）。
6. MISSING: Riskfolio-Lib已安装但8_组合优化.py只显示了HRP权重数字表格。添加有效前沿散点图和协方差矩阵热力图。
7. MISSING: pipeline.py有compare_topics函数但UI从未使用。添加跨主题对比视图（至少把AI算力vs机器人vs新能源前三名对比展示）。
8. MISSING: 报告页只有一个st.markdown。改为分章节render（摘要/事件/产业链/股票列表/风险/回测），每章嵌入对应图表。
9. MISSING: 所有页面加载后完全静态，没有金融系统该有的"仪表盘感"。在首页加载一个综合仪表盘（市场概览+热点扫描+风险预警+交易信号），至少3个动态指标。

【修改范围】
只改以下文件：
- ui/app.py（修复乱码 + 仪表盘section）
- ui/pages/1_事件分析.py 到 8_组合优化.py（按上面逐项修）
- ui/components/charts.py（添加K线图函数）
- src/backtest_adapter.py（接入quantstats）

【禁止行为】
- 不要新建文件
- 不要删除任何已有功能
- 不要碰 tests/ 目录
- 不要碰 data/demo_state.json
- 不要碰 src/factor_engine.py（技术因子计算已经正确）
- 不要只说"已完成"——每条修复必须有对应的终端验证输出

【验收方式】
python -m pytest tests/test_batch_api.py -x -q  # 必须4/4 pass
python -c "from src.pipeline import load_demo_state; r=load_demo_state('低空经济'); print(r.get('chain')); assert len(r.get('chain',[])) > 0"  # 链不能为0
streamlit run ui/app.py  # 在浏览器检查：
  1) 首页有仪表盘（不是空白）
  2) 回测页有K线图
  3) 多因子页有技术指标section
  4) 组合优化页有散点图+热力图
  5) 报告页不是纯文字

【记住】
- 我说"没感觉有什么太大区别"是因为界面还是太静态了
- 不要骗我——每一条用终端命令验证，不要用print总结代替验证
- 一次修完所有9条，不要选择性跳过
