"""昇腾云端 LLM 调用封装 (OpenAI Chat Completions 兼容)。

实测结论(2026-07-31):
- GitCode 平台模型 zai-org/GLM-5.2 可正常调用 (OpenAI 格式)
- 单请求响应约 3~4 秒 -> 并发必须限流 (QPS 限制)
- 输出可能非纯 JSON -> 需 json-repair 清洗 + 代码层兜底

B4 多模型分工:
- event: GLM-5.2 (事件理解)
- chain: Qwen3-4B (产业链推理, 轻量快速)
- deep: DeepSeek-V4-Pro (深度分析)
- report: GLM-5.2 (报告生成, 长文本)
单次分析调用预算: LLM_CALL_BUDGET (默认8次)
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 单次分析昇腾调用计数 (线程隔离: 并发下各线程独立预算, 避免全局共享误杀)
_CALL_COUNT: Dict[str, int] = {"total": 0}
_thread_local_calls = threading.local()
_thread_local_calls.calls = 0


def reset_call_count() -> None:
    """重置调用计数 (每次 run_analysis 开始调用)。线程局部。"""
    _CALL_COUNT["total"] = 0
    _thread_local_calls.calls = 0


def get_call_count() -> int:
    """当前分析已用昇腾调用次数 (线程局部, 无则取全局)。"""
    return getattr(_thread_local_calls, "calls", _CALL_COUNT["total"])

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from json_repair import repair_json
    _HAS_JSON_REPAIR = True
except ImportError:
    _HAS_JSON_REPAIR = False


def _clean_json(text: str) -> Optional[Dict[str, Any]]:
    """清洗 LLM 输出, 尽量还原为 JSON dict。失败返回 None。"""
    if not text:
        return None
    text = text.strip()
    # 去掉可能的 ```json 代码块围栏
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:] if lines and lines[0].startswith("```") else lines
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # 截取第一个 { 到最后一个 }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]

    for attempt in (0, 1):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if attempt == 0 and _HAS_JSON_REPAIR:
                fixed = repair_json(text)
                if fixed and fixed != text:
                    text = fixed
                    continue
            return None
    return None


def chat_completion(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    retries: int = 2,
    timeout: Optional[float] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """调用昇腾云 LLM。失败返回 None (调用方兜底)。

    timeout: 单次请求超时(秒), 默认用 config.REQUEST_TIMEOUT_LLM。
             长文本生成(如研究报告)应传入更长超时。
    model: 指定模型 (B4 多模型分工)。默认用 config.ASCEND_MODEL。
           可选: "event"/"chain"/"deep"/"report" 或直接模型名。
    """
    from config import (
        ASCEND_API_BASE, ASCEND_API_KEY, ASCEND_MODEL,
        LLM_MODELS, LLM_MODEL_TIMEOUTS, LLM_CALL_BUDGET, REQUEST_TIMEOUT_LLM,
    )

    if not _HAS_REQUESTS or not ASCEND_API_KEY:
        logger.warning("缺少 requests 库或 ASCEND_API_KEY, 无法调用 LLM")
        return None

    # 多模型路由: 角色 -> 模型名
    effective_model = ASCEND_MODEL
    role = None
    if model:
        if model in LLM_MODELS:
            role = model
            effective_model = LLM_MODELS[model]
        else:
            effective_model = model  # 直接传模型名

    # 调用预算控制 (防超成本, 达到上限即阻断, 不再放行)
    if get_call_count() >= LLM_CALL_BUDGET:
        logger.error("昇腾调用已达预算上限 %d 次, 本次调用被阻断", LLM_CALL_BUDGET)
        return None
    _thread_local_calls.calls += 1
    _CALL_COUNT["total"] += 1

    # 超时: 显式指定优先, 其次按角色推荐, 最后默认
    if timeout is None:
        timeout = LLM_MODEL_TIMEOUTS.get(role, REQUEST_TIMEOUT_LLM)
    effective_timeout = timeout

    url = f"{base_url}/chat/completions"
    payload = {
        "model": effective_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(retries + 1):
        t_start = time.time()
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=effective_timeout)
            r.raise_for_status()
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            # 监控记录 (B4/Phase2)
            try:
                from src.ascend_monitor import monitor
                monitor.record_call(True, time.time() - t_start, effective_model)
            except ImportError:
                pass
            return content
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM 调用失败(第%d次): %s", attempt + 1, str(e)[:120])
            # 监控记录失败
            try:
                from src.ascend_monitor import monitor
                monitor.record_call(False, time.time() - t_start, effective_model)
            except ImportError:
                pass
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    return None


def chat_json(system: str, user: str, **kwargs) -> Optional[Dict[str, Any]]:
    """调用 LLM 并要求输出 JSON, 自动清洗。失败返回 None。"""
    content = chat_completion(system, user, **kwargs)
    if content is None:
        return None
    return _clean_json(content)


# 异步调用共享线程池 (避免每次调用新建线程且永不关闭导致线程泄漏)
_executor: Any = None
_executor_lock = threading.Lock()


def _get_async_executor():
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                from concurrent.futures import ThreadPoolExecutor
                _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-async")
    return _executor


def async_chat_completion(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    retries: int = 2,
    timeout: Optional[float] = None,
    model: Optional[str] = None,
) -> Any:
    """异步调用昇腾 LLM (返回可 await 的 future)。

    Windows 兼容: 用 ThreadPoolExecutor 包装同步调用, 无 asyncio 平台依赖。
    用法:
        future = async_chat_completion(system, user)
        content = future.result(timeout=60)
    """
    from config import LLM_CALL_BUDGET

    if _CALL_COUNT["total"] >= LLM_CALL_BUDGET:
        logger.error("昇腾调用已达预算上限 %d 次, 本次异步调用被阻断", LLM_CALL_BUDGET)
        from concurrent.futures import Future

        future: Future = Future()
        future.set_result(None)
        return future

    return _get_async_executor().submit(
        chat_completion, system, user, temperature, max_tokens,
        retries, timeout, model,
    )

def chat_completion_with_tools(
    messages: list,
    tools: Optional[list] = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    retries: int = 1,
    timeout: Optional[float] = None,
    model: Optional[str] = None,
    provider: str = "ascend",
) -> Optional[Dict[str, Any]]:
    """带工具调用的 LLM 调用 (OpenAI function-calling 兼容), 供 ReAct 编排器使用。

    messages: [{"role": "system"/"user"/"assistant"/"tool", ...}]
    tools: OpenAI 工具 schema 列表 ([{"type":"function","function":{...}}])。
    返回: {"content": str, "tool_calls": [{"id","type","function":{"name","arguments"}}]}
    - 平台不支持 tools 字段时自动降级为纯文本 (tool_calls 为空列表)。
    - 预算/超时/重试/监控与 chat_completion 一致。
    """
    from config import (
        ASCEND_API_BASE, ASCEND_API_KEY, ASCEND_MODEL,
        LLM_MODELS, LLM_MODEL_TIMEOUTS, LLM_CALL_BUDGET, REQUEST_TIMEOUT_LLM,
        ZHIPU_API_BASE, ZHIPU_API_KEY, ZHIPU_MODEL,
    )

    # 提供方选择: provider="zhipu" 且配置了 key 时走智谱 (快且稳), 否则昇腾
    if provider == "zhipu" and ZHIPU_API_KEY:
        base_url = ZHIPU_API_BASE
        api_key = ZHIPU_API_KEY
        effective_model = model or ZHIPU_MODEL
        role = None
    else:
        if provider == "zhipu":
            logger.warning("未配置 ZHIPU_API_KEY, 回落昇腾提供方")
        base_url = ASCEND_API_BASE
        api_key = ASCEND_API_KEY
        effective_model = ASCEND_MODEL
        role = None
        if model:
            if model in LLM_MODELS:
                role = model
                effective_model = LLM_MODELS[model]
            else:
                effective_model = model

    if not _HAS_REQUESTS or not api_key:
        logger.warning("缺少 requests 库或 API Key, 无法调用 LLM")
        return None

    # 调用预算控制 (与 chat_completion 一致, 达到上限即阻断)
    if get_call_count() >= LLM_CALL_BUDGET:
        logger.error("昇腾调用已达预算上限 %d 次, 本次调用被阻断", LLM_CALL_BUDGET)
        return None
    _thread_local_calls.calls += 1
    _CALL_COUNT["total"] += 1

    if timeout is None:
        timeout = LLM_MODEL_TIMEOUTS.get(role, REQUEST_TIMEOUT_LLM)

    url = f"{ASCEND_API_BASE}/chat/completions"
    payload: Dict[str, Any] = {
        "model": effective_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    headers = {
        "Authorization": f"Bearer {ASCEND_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(retries + 1):
        t_start = time.time()
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            msg = (data.get("choices") or [{}])[0].get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
            try:
                from src.ascend_monitor import monitor
                monitor.record_call(True, time.time() - t_start, effective_model)
            except ImportError:
                pass
            return {"content": content, "tool_calls": tool_calls}
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM(tools) 调用失败(第%d次): %s", attempt + 1, str(e)[:120])
            try:
                from src.ascend_monitor import monitor
                monitor.record_call(False, time.time() - t_start, effective_model)
            except ImportError:
                pass
            # 平台不支持 tools 字段时去掉后重试一次纯文本
            if attempt == 0 and tools:
                payload.pop("tools", None)
                payload.pop("tool_choice", None)
                continue
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    return None

