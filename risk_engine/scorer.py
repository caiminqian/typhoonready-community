"""复合风险评分：台风接近度(40) + 降雨强度(30) + 地形内涝(30) = 100 分。

规则全部显式写死、可解释：每个因子输出分数和一句话原因，
评审/用户能一眼看懂"为什么是高风险"，不搞黑箱。
"""
from __future__ import annotations

import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """两点间大圆距离（公里）。"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def score_typhoon(points: list[dict], lat: float, lon: float) -> tuple[float, str]:
    """台风接近度评分（满分 40）：72 小时预报路径距目标的最近距离 + 风速加成。"""
    if not points:
        return 0.0, "无台风路径数据"
    dists = [haversine_km(lat, lon, p["lat"], p["lon"]) for p in points]
    min_d = min(dists)
    max_wind = max((p.get("wind_ms") or 0) for p in points)
    # 距离分档
    if min_d < 100:
        base = 40.0
    elif min_d < 200:
        base = 32.0
    elif min_d < 300:
        base = 24.0
    elif min_d < 500:
        base = 15.0
    elif min_d < 800:
        base = 8.0
    else:
        base = 0.0
    # 风速加成：强台风威胁更大
    mult = 1.2 if max_wind >= 50 else (1.1 if max_wind >= 35 else 1.0)
    score = min(40.0, base * mult)
    reason = f"台风 72 小时路径最近距目标约 {min_d:.0f} 公里，最大风速 {max_wind:.0f} 米/秒"
    return round(score, 1), reason


def score_rainfall(daily: list[dict]) -> tuple[float, str]:
    """降雨强度评分（满分 30）：取未来 3 天最大 24 小时雨量。"""
    if not daily:
        return 0.0, "无降雨预报数据"
    max_mm = max(d.get("mm_24h", 0) for d in daily)
    if max_mm >= 250:
        score = 30.0
    elif max_mm >= 150:
        score = 24.0
    elif max_mm >= 100:
        score = 18.0
    elif max_mm >= 50:
        score = 12.0
    elif max_mm >= 25:
        score = 6.0
    else:
        score = 0.0
    reason = f"未来 3 天最大 24 小时降雨量 {max_mm:.0f} 毫米"
    return score, reason


def score_terrain(zone: dict, max_rain_mm: float = 0) -> tuple[float, str]:
    """地形内涝评分（满分 30）：静态底图分 + 实时降雨放大。

    内涝底图（等级/高程/历史）是静态的、没有公开实时接口；
    动态部分来自实时降雨预报：预报雨越大，低洼小区的内涝分放大越多。
    复盘模式（雨量 <50mm）加成0，历史演示数字不受影响。
    """
    level = int(zone.get("zone_level", 0))
    base = {3: 30.0, 2: 20.0, 1: 10.0}.get(level, 3.0)
    if max_rain_mm >= 150:
        bonus = 10.0
    elif max_rain_mm >= 100:
        bonus = 6.0
    elif max_rain_mm >= 50:
        bonus = 3.0
    else:
        bonus = 0.0
    score = min(30.0, base + bonus)
    history = zone.get("history", "")
    reason = (f"小区内涝风险 {level} 级（0-3 级），高程 {zone.get('elevation_m', '?')} 米；{history}"
              + (f"；叠加未来 3 天最大 {max_rain_mm:.0f} 毫米降雨，地形分 +{bonus:.0f}（实时降雨放大）"
                 if bonus else ""))
    return round(score, 1), reason


def level_of(score: float) -> str:
    if score >= 75:
        return "极高"
    if score >= 55:
        return "高"
    if score >= 30:
        return "中"
    return "低"


def assess(typhoon: dict, rainfall: dict, zone: dict, lat: float, lon: float) -> dict:
    """主入口：返回包含分项解释的风险报告。"""
    s1, r1 = score_typhoon(typhoon.get("points", []), lat, lon)
    s2, r2 = score_rainfall(rainfall.get("daily", []))
    max_rain = max((d.get("mm_24h", 0) for d in rainfall.get("daily", [])), default=0)
    s3, r3 = score_terrain(zone, max_rain)
    total = round(s1 + s2 + s3, 1)
    return {
        "score": total,
        "level": level_of(total),
        "factors": [
            {"name": "台风接近度", "score": s1, "max": 40, "reason": r1},
            {"name": "降雨强度", "score": s2, "max": 30, "reason": r2},
            {"name": "地形内涝", "score": s3, "max": 30, "reason": r3},
        ],
        "typhoon_name": typhoon.get("name", "未知"),
    }
