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


def _template_guidance(risk: dict, community: dict, zone: dict, context: dict) -> dict:
    """降级模板：风险等级定制 + 数据驱动开头，不说空话。"""
    level = risk["level"]
    items = {k: list(v) for k, v in FALLBACK_TEMPLATES.items()}
    # 各等级优先动作，插到 72h 最前面
    priority = {
        "极高": ["立即联系社区确认避险安置点位置和转移路线",
                 "一楼住户今晚前把贵重物品搬到高处"],
        "高": ["提前规划紧急转移路线并告知家人",
               "24小时内把地下车库车辆移到高处"],
        "中": ["关注预报更新，雨势加大时升级防范"],
        "低": ["常规防范即可，留意预报变化"],
    }.get(level, [])
    if priority:
        items["72h"] = priority + items["72h"]
    # 低风险时精简 6h 清单，避免制造恐慌
    if level == "低":
        items["6h"] = ["台风对本小区影响较小，6小时内无特殊行动，保持关注即可"]
    summary = (f"{risk['typhoon_name']}未来72小时最近距本小区约 "
               f"{context['min_dist_km']:.0f} 公里，"
               f"最大风速 {context['max_wind_ms']:.0f} 米/秒，"
               f"未来3天最大24小时降雨 {context['max_rain_mm']:.0f} 毫米。")
    # 压线从严：点估计为中/低，但蒙特卡洛显示高及以上概率不可忽略时，加严提醒
    uq = risk.get("uncertainty") or {}
    p_hp = uq.get("p_high_plus", 0)
    if level in ("中", "低") and p_hp >= 0.3:
        items["72h"] = [f"注意：综合评分为{level}，但不确定性分析显示高风险概率达 "
                        f"{p_hp:.0%}，建议按高一档做防范"] + items["72h"]
    return {"mode": "template", "header": FALLBACK_HEADER,
            "summary": summary, "timelines": items}


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
            result = _template_guidance(risk, community, zone, context)
            result["header"] += f"；LLM 调用失败（{e}）"
            return result
    return _template_guidance(risk, community, zone, context)
