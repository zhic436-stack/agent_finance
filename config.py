"""agent_finance 全局配置。

所有可调参数集中于此。实测结论(2026-07-31)驱动的关键适配:
- 东财对 python requests 有 TLS 指纹风控 -> 数据采集统一用 curl_cffi
- akshare 的 stock_a_lg_indicator 已移除 -> 估值用 stock_value_em
- stock_news_em 新闻滞后约1.5个月 -> 定位为"近期新闻"而非"当日新闻"
- 东财概念接口需翻页(单页100) + 降频(0.8~1.2s) + 指数退避重试
"""
import os
from pathlib import Path

# 自动加载 .env (若存在), 使 ASCEND_API_KEY 等配置在 UI 启动时生效
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv 未安装时依赖系统环境变量

# ============ 路径 ============
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OFFLINE_DIR = DATA_DIR / "offline"
RULES_FILE = DATA_DIR / "industry_chains.json"

# ============ 昇腾 API 配置 ============
ASCEND_API_BASE = os.getenv("ASCEND_API_BASE", "https://api-ai.gitcode.com/v1")
ASCEND_API_KEY = os.getenv("ASCEND_API_KEY", "")
ASCEND_MODEL = os.getenv("ASCEND_MODEL", "zai-org/GLM-5.2")

# 智谱 LLM 提供方 (可选, OpenAI 兼容): 响应快且稳, 用于 Agent 路径的稳定收敛
# 未配置 ZHIPU_API_KEY 时 Agent 自动回落昇腾
ZHIPU_API_BASE = os.getenv("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
ZHIPU_MODEL = os.getenv("ZHIPU_MODEL", "glm-4-flash")

# 昇腾多模型分工 (B4, 全部实测可用)
LLM_MODELS = {
    "event": "zai-org/GLM-5.2",              # 事件理解
    "chain": "Qwen/Qwen3-4B-Instruct-2507",  # 产业链推理 (轻量快速)
    "deep": "deepseek-ai/DeepSeek-V4-Pro",   # 深度分析
    "report": "zai-org/GLM-5.2",             # 报告生成 (长文本)
}
# 各角色推荐超时 (秒) — 实测 chain 模型响应较慢需 60s
LLM_MODEL_TIMEOUTS = {
    "event": 45,
    "chain": 60,
    "deep": 60,
    "report": 90,
}
# 单次分析昇腾调用上限 (成本控制)
LLM_CALL_BUDGET = 8
LLM_TOKEN_BUDGET = 10000

# ============ 东财接口(实测确认可用的数据链路) ============
EM_CLIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"           # 概念列表/成分股快照
EM_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"  # 历史行情
EM_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"  # 板块成分股

# ============ 数据采集 ============
AKSHARE_TIMEOUT = 10            # akshare 单次超时(秒)
REQUEST_TIMEOUT = 15            # curl_cffi 单次超时(秒)
MAX_RETRIES = 4                 # 指数退避最大重试次数
BASE_DELAY = 1.0                # 重试基础延迟(秒)
MIN_REQUEST_INTERVAL = 0.8      # 降频最小间隔(秒)
MAX_REQUEST_INTERVAL = 1.2      # 降频最大间隔(秒)
CONCEPT_PAGE_SIZE = 100         # 东财列表单页条数(实测固定100)
MAX_CONCEPT_PAGES = 30          # 概念列表最大翻页数

# ============ 缓存 ============
CACHE_TTL = 30                  # 分钟

# ============ 因子权重 ============
WEIGHTS = {
    "event": 0.30,
    "value": 0.25,
    "growth": 0.25,
    "market": 0.20,
}

# 事件逻辑因子权重 (B3 新增, 可调)
EVENT_LOGIC_WEIGHTS = {
    "event_strength": 0.4,   # 事件强度
    "chain_position": 0.3,   # 产业链位置
    "logic_certainty": 0.3,  # 逻辑确定性
}

# 事件强度评分表 (政策等级)
POLICY_LEVEL_SCORE = {
    "国务院": 100, "国家": 100, "部委": 80, "中央": 90,
    "地方": 60, "行业": 50, "公司": 30, "其他": 20,
}
# 事件时效 (天 -> 分)
EVENT_AGE_SCORES = [(0, 100), (3, 80), (7, 50), (float("inf"), 20)]
# 逻辑确定性
LOGIC_CERTAINTY = {
    "已落地": 90, "规划": 60, "概念": 30, "其他": 40,
}

# ============ 候选股数量 ============
MAX_CANDIDATES = 30
TOP_STOCKS = 10

# ============ 并发控制 ============
CONCURRENT_LIMIT = 3
REQUEST_TIMEOUT_LLM = 15
MAX_RETRIES_LLM = 2

# ============ 离线包 ============
OFFLINE_TOPICS = [
    "低空经济", "AI算力", "机器人", "新能源",
    "半导体", "人工智能", "新能源汽车", "光伏", "军工", "消费电子",
]
OFFLINE_FILES = {
    "低空经济": "low_altitude_economy.json",
    "AI算力": "ai_compute.json",
    "机器人": "robot.json",
    "新能源": "new_energy.json",
    "半导体": "semiconductor.json",
    "人工智能": "ai.json",
    "新能源汽车": "new_energy_vehicle.json",
    "光伏": "solar.json",
    "军工": "defense.json",
    "消费电子": "consumer_electronics.json",
}

# ============ 概念别名映射(东财板块名 -> 标准名) ============
CONCEPT_ALIAS = {
    "AI算力": "算力概念",
    "机器人": "机器人概念",
    "新能源": "新能源",
    "低空经济": "低空经济",
}

# ============ 风险判定阈值 ============
RISK_LOW_VOL = 0.20      # 低风险: 波动率 < 0.20
RISK_LOW_DRAWDOWN = 0.15 # 低风险: 最大回撤 < 0.15
RISK_LOW_PE_PCT = 0.60   # 低风险: PE分位 < 0.60
RISK_MID_VOL = 0.35      # 中风险: 波动率 < 0.35
RISK_MID_DRAWDOWN = 0.25 # 中风险: 最大回撤 < 0.25

# ============ 财务演示数据 ============
# 真实财务数据缺失时, 是否用"演示数据"兜底 (仅黑客松演示, 非真实投资数据)
# 默认关闭: 保持因子引擎"无数据=0分"的语义; demo_prep 生成演示数据时置 True
DEMO_DATA_FALLBACK = bool(os.getenv("DEMO_DATA_FALLBACK", "0") in ("1", "true", "True"))

# ============ 回测配置 ============
BACKTEST_CONFIG = {
    "initial_capital": 1_000_000,
    "commission_rate_buy": 0.00015,    # 买入佣金 万1.5
    "commission_rate_sell": 0.00015,   # 卖出佣金 万1.5
    "stamp_tax_rate": 0.001,           # 卖出印花税 千1
    "slippage": 0.001,                 # 滑点 0.1%
    "max_position_pct": 0.10,          # 单票仓位上限 10%
    "limit_up_threshold": 0.095,       # 涨停阈值(禁止买入)
    "limit_down_threshold": -0.095,    # 跌停阈值(禁止卖出)
    "cash_interest_rate": 0.015,       # 空仓资金国债逆回购年化 1.5%
}

# ============ 监控配置 ============
MONITOR_CONFIG = {
    "alert_threshold": 5,              # 信号变化超阈值触发预警
    "daily_report_time": "16:00",
}

# ============ 数据更新配置 ============
UPDATE_CONFIG = {
    "data_freshness_days": 1,          # 数据超过 N 个交易日告警
    "auto_update_enabled": False,
    "update_time": "15:30",
}
