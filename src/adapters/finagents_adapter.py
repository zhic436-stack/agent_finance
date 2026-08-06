"""FinAgents 适配器: 多智能体编排架构映射 (补漏块5.1)。

借鉴 poetony/FinAgents 的多智能体工作流模式 (RESEARCHER -> ANALYST -> RISK -> MANAGER),
将其编排思想映射到本项目 pipeline 的既有能力上。

适配原则:
- 不捆绑 FinAgents 的 FastAPI/PostgreSQL 全套 (本项目独立运行)
- 复用其工作流节点类型, 用 pipeline 的模块实现各 agent 角色
- 提供 FinAgentsPipeline 类, 输出与 FinAgents NodeType 同构的编排轨迹

验证: python -c "from src.adapters.finagents_adapter import FinAgentsPipeline; print('OK')"
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 对应 FinAgents NodeType 的角色枚举
ROLES = ["researcher", "analyst", "risk", "manager"]


class FinAgentsPipeline:
    """多智能体金融分析管道 (FinAgents 编排模式)。"""

    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self.steps: List[Dict[str, Any]] = []

    def _record(self, role: str, action: str, detail: str = "") -> None:
        self.steps.append({"role": role, "action": action, "detail": detail})

    def run(self, topic: str, max_candidates: int = 10) -> Dict[str, Any]:
        """执行完整多智能体分析。"""
        from src.pipeline import run_analysis

        # 1. RESEARCHER: 事件理解 + 产业链推理 + 研究假设
        self._record("researcher", "事件理解", f"解析事件: {topic}")
        result = run_analysis(topic, use_llm=self.use_llm,
                              max_candidates=max_candidates, enrich_market=False)
        event = result.get("event", {})
        chain = result.get("chain", [])
        hypothesis = result.get("hypothesis", {})
        self._record("researcher", "产业链推理", f"{len(chain)} 个受益环节")
        self._record("researcher", "研究假设", hypothesis.get("core_logic", "")[:60])

        # 2. ANALYST: 四因子 + 事件逻辑因子
        stock_results = result.get("stock_results", [])
        top = sorted(stock_results, key=lambda r: r.get("factors", {}).get("composite", 0), reverse=True)[:5]
        self._record("analyst", "因子分析", f"{len(stock_results)} 只候选股, Top5: "
                     f"{[r['stock'].name for r in top if r.get('stock')]}")

        # 3. RISK: 风险分级
        high = sum(1 for r in stock_results if r.get("risk", {}).get("risk_level") == "高")
        self._record("risk", "风险评估", f"高风险 {high}/{len(stock_results)}")

        # 4. MANAGER: 汇总报告
        self._record("manager", "报告生成", f"{len(result.get('report', ''))} 字")

        result["agent_steps"] = self.steps
        result["agent_count"] = len(ROLES)
        return result


def adapt_chain_to_nodes(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将产业链环节转为 FinAgents NodeDefinition 同构结构。"""
    nodes = []
    for i, node in enumerate(chain):
        nodes.append({
            "id": str(i),
            "type": "analyst" if i == 0 else "researcher",
            "name": node.get("name", ""),
            "description": node.get("description", ""),
        })
    return nodes


if __name__ == "__main__":
    p = FinAgentsPipeline(use_llm=False)
    r = p.run("低空经济", max_candidates=5)
    print("OK")
    print(f"Agent步骤: {len(r['agent_steps'])} | 角色: {r['agent_count']}")
    for s in r["agent_steps"]:
        print(f"  [{s['role']}] {s['action']}: {s['detail'][:40]}")
