"""40/30/30 权重敏感性分析。

问题：降雨权重 w_r 在 10~50 之间漂移时，总分、风险等级、
以及"挪车"结论是否稳定？

挪车定义（对应 guidance/generator.py 模板逻辑）：
- 挪车（一般）：72h 模板恒含"把停在低洼处的车辆移到地势高的地方"，
  与权重无关，恒成立。
- 挪车（紧急）：level 在 {高, 极高} 时模板追加"24小时内把地下车库车辆移到高处"。
  本分析检验"紧急挪车"结论对权重的敏感性。

权重扰动方式（保持总和 100）：
- 单因子扰动：w_r 取 10~50（步长 2.5），w_t 与 w_terr 按 40:30 比例分剩余。
- 对 w_t 同样做 20~60 扰动，作对照。
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from risk_engine.scorer import level_of

BASE_W = (40.0, 30.0, 30.0)  # 台风 / 降雨 / 地形

# 场景：(名称, 台风分/40, 降雨分/30, 地形分/30, 说明)
SCENARIOS = [
    ("繁裕小区·实况(静风期)", 0.0, 0.0, 20.0, "蔷琵远离、无降雨，风险全来自地形"),
    ("景元小区·实况(静风期)", 0.0, 0.0, 30.0, "3级内涝区，静态分拉满"),
    ("书院社区·贝碧嘉复盘", 40.0, 6.0, 20.0, "IBTrACS真实路径+ERA5降雨，66分"),
    ("合成·暴雨型", 8.0, 24.0, 20.0, "台风远但强降雨（180mm/24h档）"),
    ("合成·台风逼近型", 32.0, 12.0, 14.0, "台风320km内+中雨，2级内涝区"),
    ("合成·临界型", 24.0, 12.0, 10.0, "故意凑近55分界，测翻转"),
]


def score_with_weights(t, r, terr, w_t, w_r, w_terr):
    return round(w_t * t / 40 + w_r * r / 30 + w_terr * terr / 30, 2)


def vary_rain(t, r, terr, w_r):
    w_t = 40 * (100 - w_r) / 70
    w_terr = 30 * (100 - w_r) / 70
    return score_with_weights(t, r, terr, w_t, w_r, w_terr)


def vary_typhoon(t, r, terr, w_t):
    w_r = 30 * (100 - w_t) / 70
    w_terr = 30 * (100 - w_t) / 70
    return score_with_weights(t, r, terr, w_t, w_r, w_terr)


def urgent_move(level):
    return level in ("高", "极高")


def main():
    print("=" * 78)
    print("权重敏感性分析：降雨权重 w_r 在 [10, 50]（步长2.5），其余按 40:30 比例分配")
    print("=" * 78)
    for name, t, r, terr, desc in SCENARIOS:
        base = score_with_weights(t, r, terr, *BASE_W)
        base_lv = level_of(base)
        flips = []
        prev_lv = None
        w = 10.0
        min_s, max_s = 1e9, -1e9
        while w <= 50.0:
            s = vary_rain(t, r, terr, w)
            lv = level_of(s)
            min_s, max_s = min(min_s, s), max(max_s, s)
            if prev_lv is not None and lv != prev_lv:
                flips.append((round(w, 1), prev_lv, lv))
            prev_lv = lv
            w += 2.5
        urg = set()
        w = 10.0
        while w <= 50.0:
            urg.add(urgent_move(level_of(vary_rain(t, r, terr, w))))
            w += 2.5
        print(f"\n【{name}】{desc}")
        print(f"  基准(40/30/30)：{base} 分 -> {base_lv}")
        print(f"  w_r在[10,50] 时总分区间：[{min_s}, {max_s}]（振幅 {round(max_s - min_s, 1)}）")
        if flips:
            for w_f, a, b in flips:
                print(f"  [翻转] w_r={w_f}：{a} -> {b}")
        else:
            print("  [稳定] 等级无翻转")
        if len(urg) == 1:
            print(f"  [稳定] 紧急挪车结论：{'触发' if list(urg)[0] else '不触发'}（权重漂移不改变）")
        else:
            print("  [注意] 紧急挪车结论随权重翻转！")

    print("\n" + "=" * 78)
    print("对照：台风权重 w_t 在 [20, 60] 扰动时的等级翻转")
    print("=" * 78)
    for name, t, r, terr, desc in SCENARIOS:
        flips = []
        prev_lv = None
        w = 20.0
        while w <= 60.0:
            lv = level_of(vary_typhoon(t, r, terr, w))
            if prev_lv is not None and lv != prev_lv:
                flips.append((round(w, 1), prev_lv, lv))
            prev_lv = lv
            w += 2.5
        msg = "无翻转" if not flips else "; ".join(f"w_t={x} {a}->{b}" for x, a, b in flips)
        print(f"  {name}: {msg}")

    with open("analysis/sensitivity.csv", "w", encoding="utf-8") as f:
        f.write("scenario,w_rain,score,level\n")
        for name, t, r, terr, _ in SCENARIOS:
            w = 10.0
            while w <= 50.0:
                s = vary_rain(t, r, terr, w)
                f.write(f"{name},{w:.1f},{s},{level_of(s)}\n")
                w += 2.5
    print("\nCSV 已写入 analysis/sensitivity.csv")


if __name__ == "__main__":
    main()
