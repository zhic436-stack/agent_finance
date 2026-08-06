"""LLM 响应结构化解析器: 处理大模型非标准输出, 提取结构化数据。

兼容: ```json 围栏 / 全角标点 / 多余文本 / 字段缺失。
与 llm.py 的 _clean_json 互补: 本模块提供含默认值填充的完整解析。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from json_repair import repair_json
    _HAS_REPAIR = True
except ImportError:
    _HAS_REPAIR = False


def extract_json_block(text: str) -> Optional[str]:
    """从文本中提取最可能的 JSON 块 (优先 ```json 围栏, 其次首尾大括号)。"""
    if not text:
        return None
    text = text.strip()

    # 1. ```json ... ``` 围栏
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 2. 首尾大括号 (含嵌套)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return None


def _fix_common_issues(text: str) -> str:
    """修复常见 LLM 输出问题 (全角标点/多余逗号/中文冒号)。"""
    fixed = text
    # 全角标点 -> 半角
    fixed = fixed.replace("，", ",").replace("：", ":")
    # 去掉 JSON 内非法尾逗号 (粗略: 逗号后紧跟 } ])
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    return fixed


def parse_llm_response(response: str, expected_format: Dict[str, Any]) -> Dict[str, Any]:
    """解析 LLM 响应, 填充默认值。任何情况不抛异常。

    参数:
        response: LLM 原始输出
        expected_format: {字段名: 默认值} 模板

    返回: 完整字段 dict (缺失字段用默认值)。
    """
    result = dict(expected_format)
    if not response:
        return result

    block = extract_json_block(response)
    if block is None:
        logger.warning("LLM 响应无 JSON 块, 返回默认: %.60s", response[:60])
        return result

    # 尝试解析 (原始 -> 修复 -> json-repair)
    data: Optional[dict] = None
    for candidate in (block, _fix_common_issues(block)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                data = parsed
                break
        except json.JSONDecodeError:
            continue

    if data is None and _HAS_REPAIR:
        try:
            repaired = repair_json(block)
            if repaired:
                data = json.loads(repaired) if isinstance(json.loads(repaired), dict) else None
        except (json.JSONDecodeError, TypeError):
            data = None

    if data is None:
        # 兜底: 正则提取字段
        return _fallback_parse(block, expected_format)

    # 合并: 只覆盖存在的键, 缺失保持默认
    for key in expected_format:
        if key in data:
            result[key] = data[key]
    return result


def _fallback_parse(text: str, expected_format: Dict[str, Any]) -> Dict[str, Any]:
    """兜底解析: 正则提取 "key": "value"。"""
    result = dict(expected_format)
    for key in expected_format:
        # 匹配 "key": "value" 或 "key": value
        m = re.search(rf'"{key}"\s*:\s*"?([^",}}\]]+)"?', text)
        if m:
            result[key] = m.group(1).strip()
    return result
