"""指引生成器：优先调 LLM，无 key 时降级为规则模板。

LLM 接入方式：环境变量
  AI4C_LLM_API_KEY   - OpenAI 兼容接口的 key
  AI4C_LLM_BASE_URL  - 接口地址（默认 https://api.openai.com/v1）
  AI4C_LLM_MODEL     - 模型名（默认 gpt-4o-mini）
只用标准库 urllib，不引入 openai 依赖。
"""
from __future__ import annotations

import json
import os
import urllib.request

from .prompts import (
    FALLBACK_HEADER,
    FALLBACK_TEMPLATES,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)


def _call_llm(system: str, user: str) -> str:
    """调 OpenAI 兼容的 chat completions 接口，返回文本。"""
    api_key = os.environ["AI4C_LLM_API_KEY"]
    base_url = os.environ.get("AI4C_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("AI4C_LLM_MODEL", "gpt-4o-mini")
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url + "/chat/completions", data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _template_guidance(risk: dict, community: dict, zone: dict) -> dict:
    """降级模板：把风险数据拼进固定话术。"""
    header = FALLBACK_HEADER
    items = {k: list(v) for k, v in FALLBACK_TEMPLATES.items()}
    # 按风险等级追加一条定制提醒
    extra = {
        "极高": "本小区风险极高，请务必提前联系社区确认避险安置点位置",
        "高": "本小区风险较高，建议提前规划好紧急转移路线",
        "中": "保持关注预报更新，雨势加大时再升级防范",
        "低": "常规防范即可，留意预报变化",
    }.get(risk["level"], "")
    if extra:
        items["72h"] = [extra] + items["72h"]
    return {"mode": "template", "header": header, "timelines": items}


def generate(risk: dict, community: dict, zone: dict, context: dict) -> dict:
    """主入口。context 含 min_dist_km / max_wind_ms / max_rain_mm，供模板填充。"""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        community_name=community["name"],
        address=community["address"],
        typhoon_name=risk["typhoon_name"],
        min_dist_km=context["min_dist_km"],
        max_wind_ms=context["max_wind_ms"],
        max_rain_mm=context["max_rain_mm"],
        zone_level=zone.get("zone_level", "?"),
        zone_history=zone.get("history", ""),
        score=risk["score"],
        level=risk["level"],
    )
    if os.environ.get("AI4C_LLM_API_KEY"):
        try:
            text = _call_llm(SYSTEM_PROMPT, user_prompt)
            return {"mode": "llm", "header": "（AI 生成版指引）", "text": text}
        except Exception as e:
            # LLM 调用失败也降级，不让整条链路挂掉
            result = _template_guidance(risk, community, zone)
            result["header"] += f"；LLM 调用失败（{e}）"
            return result
    return _template_guidance(risk, community, zone)
