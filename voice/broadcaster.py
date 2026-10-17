"""语音播报：把"今晚最重要的几件事"转成 MP3。

用 Microsoft Edge Neural TTS（edge-tts 库，免费、无需 key），
中文女声 zh-CN-XiaoxiaoNeural，语速适中，适合老年用户收听。

播报文本由前端根据已有的 risk + top_actions 拼好传给 /api/speak，
后端只做 TTS 合成（按文本哈希缓存，避免重复合成）。
"""
from __future__ import annotations

import asyncio
import hashlib

import edge_tts

VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "+0%"  # 语速：默认；老年人可前端用 playbackRate 0.9 慢放
MAX_CHARS = 500


def compose_broadcast(community_name: str, risk: dict, top_actions: list) -> str:
    """拼播报文本。纯函数，前后端可复用同一逻辑（前端用 JS 版）。"""
    level = risk.get("level", "")
    score = risk.get("score", 0)
    n = len(top_actions)
    parts = [f"社区防台小助手播报。{community_name}当前风险等级{level}，{score:.0f}分。"]
    if n == 1:
        parts.append(f"今晚最重要的一件事：{top_actions[0]['text']}。")
    elif n > 1:
        parts.append(f"今晚最重要的{n}件事：")
        nums = "一二三"
        for i, a in enumerate(top_actions[:3]):
            parts.append(f"第{nums[i]}，{a['text']}；")
    return "".join(parts)


def cache_key(text: str) -> str:
    return hashlib.sha256(f"{VOICE}|{RATE}|{text}".encode("utf-8")).hexdigest()[:16]


async def _synth(text: str, path: str) -> None:
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)


def synthesize(text: str, path: str) -> None:
    """文本转 MP3 存到 path。同步封装（供 FastAPI 线程池调用）。"""
    if len(text) > MAX_CHARS:
        raise ValueError(f"播报文本超长（{len(text)}>{MAX_CHARS}）")
    asyncio.run(_synth(text, path))
