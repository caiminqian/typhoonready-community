"""不确定性量化：蒙特卡洛传播输入与权重的不确定性。

动机：气象本身是概率问题。评分器的三个因子都是分档阶梯函数，
点估计压在分档边界时（如最近距 99km vs 101km → 40 分 vs 32 分），
微小输入误差会导致总分跳变、等级翻转。本模块用蒙特卡洛给出
"分数 ± 不确定度"和"各等级概率"，让"压线从严"有据可依。

扰动模型（保守、有据、文档化）：
1. 降雨 max_mm：乘性对数正态误差 lognormal(0, 0.4)。
   NWP 0-72h 定量降水预报的相对误差典型约 ±40~50%。
2. 台风最近距 min_d：加性正态误差 normal(0, σ)，
   σ = max(50km, 0.15 × min_d)。官方路径预报误差量级：
   24h ~80km、48h ~150km、72h ~200km+；取 15% 相对误差保底 50km。
   最大风速同步扰动 ±10%（均匀）。
3. 权重：Dirichlet(α)，α=(80,60,60)，即以 (40,30,30) 为中心、
   各权重标准差约 3~4 分，对应敏感性分析中"合理分歧 ±10"的范围。
4. 地形：静态底图视为确定性输入（不扰动）；降雨放大部分
   随扰动后的 mm 自动变化。

为速度起见，MC 直接扰动标量（min_d/max_wind/max_mm），不重算每个路径点。
2000 次采样纯算术，毫秒级。
"""
from __future__ import annotations

import math
import random

from .scorer import level_of


def _score_typhoon_scalar(min_d: float, max_wind: float) -> float:
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
    mult = 1.2 if max_wind >= 50 else (1.1 if max_wind >= 35 else 1.0)
    return min(40.0, base * mult)


def _score_rainfall_scalar(max_mm: float) -> float:
    if max_mm >= 250:
        return 30.0
    if max_mm >= 150:
        return 24.0
    if max_mm >= 100:
        return 18.0
    if max_mm >= 50:
        return 12.0
    if max_mm >= 25:
        return 6.0
    return 0.0


def _score_terrain_scalar(zone_level: int, max_mm: float) -> float:
    base = {3: 30.0, 2: 20.0, 1: 10.0}.get(zone_level, 3.0)
    if max_mm >= 150:
        bonus = 10.0
    elif max_mm >= 100:
        bonus = 6.0
    elif max_mm >= 50:
        bonus = 3.0
    else:
        bonus = 0.0
    return min(30.0, base + bonus)


def _dirichlet(alpha: list[float]) -> list[float]:
    xs = [random.gammavariate(a, 1.0) for a in alpha]
    s = sum(xs)
    return [x / s * 100.0 for x in xs]


def quantify(min_d: float, max_wind: float, max_mm: float,
             zone_level: int, n: int = 2000, seed: int = 42) -> dict:
    """蒙特卡洛不确定性量化。返回分数分布与等级概率。"""
    random.seed(seed)
    scores: list[float] = []
    level_counts = {"低": 0, "中": 0, "高": 0, "极高": 0}
    for _ in range(n):
        # 1) 降雨扰动
        mm = max(0.0, max_mm * random.lognormvariate(0.0, 0.4)) if max_mm > 0 else 0.0
        # 2) 台风距离/风速扰动
        sigma_d = max(50.0, 0.15 * min_d)
        d = max(0.0, random.gauss(min_d, sigma_d))
        w = max(0.0, max_wind * random.uniform(0.9, 1.1))
        # 3) 权重扰动
        w_t, w_r, w_terr = _dirichlet([80.0, 60.0, 60.0])
        # 4) 重算三因子（按权重归一到 0-1 再加权）
        s_t = _score_typhoon_scalar(d, w) / 40.0
        s_r = _score_rainfall_scalar(mm) / 30.0
        s_terr = _score_terrain_scalar(zone_level, mm) / 30.0
        total = w_t * s_t + w_r * s_r + w_terr * s_terr
        scores.append(total)
        level_counts[level_of(total)] += 1
    scores.sort()
    mean = sum(scores) / n
    var = sum((x - mean) ** 2 for x in scores) / n
    std = math.sqrt(var)
    p = {k: round(v / n, 3) for k, v in level_counts.items()}
    return {
        "n": n,
        "score_mean": round(mean, 1),
        "score_std": round(std, 1),
        "score_p10": round(scores[int(n * 0.10)], 1),
        "score_p90": round(scores[int(n * 0.90)], 1),
        "p_level": p,
        "p_high_plus": round(p["高"] + p["极高"], 3),
        # 一句话解读，供前端/材料直接引用
        "summary": (f"蒙特卡洛 {n} 次：{mean:.0f}±{std:.0f} 分，"
                    f"P(高及以上)={p['高'] + p['极高']:.0%}"),
    }
