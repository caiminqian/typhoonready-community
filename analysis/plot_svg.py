"""从 sensitivity.csv 生成 SVG 敏感性分析图（无 matplotlib 依赖）。"""
import csv
from collections import defaultdict

W, H = 860, 520
ML, MR, MT, MB = 70, 30, 64, 60
PW, PH = W - ML - MR, H - MT - MB
X_MIN, X_MAX = 10, 50
Y_MIN, Y_MAX = 0, 90

def X(w): return ML + (w - X_MIN) / (X_MAX - X_MIN) * PW
def Y(s): return MT + PH - (s - Y_MIN) / (Y_MAX - Y_MIN) * PH

data = defaultdict(list)
with open("analysis/sensitivity.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        data[row["scenario"]].append((float(row["w_rain"]), float(row["score"]), row["level"]))

COLORS = ["#1a73e8", "#e67e22", "#27ae60", "#c0392b", "#8e44ad", "#16a085"]
NAMES = {
    "繁裕小区·实况(静风期)": "繁裕实况",
    "景元小区·实况(静风期)": "景元实况",
    "书院社区·贝碧嘉复盘": "贝碧嘉复盘",
    "合成·暴雨型": "暴雨型",
    "合成·台风逼近型": "台风逼近型",
    "合成·临界型": "临界型",
}
LEVEL_BANDS = [(75, 90, "#fadbd8", "极高"), (55, 75, "#fdebd0", "高"),
               (30, 55, "#fef9e7", "中"), (0, 30, "#eafaf1", "低")]

parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif">']
parts.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
parts.append('<text x="430" y="24" text-anchor="middle" font-size="17" font-weight="bold">降雨权重 w_r 敏感性：总分随 w_r（10~50）变化</text>')
# 等级色带
for lo, hi, col, name in LEVEL_BANDS:
    parts.append(f'<rect x="{ML}" y="{Y(hi)}" width="{PW}" height="{Y(lo)-Y(hi)}" fill="{col}" opacity="0.55"/>')
    parts.append(f'<text x="{W-8}" y="{(Y(hi)+Y(lo))/2+5}" text-anchor="end" font-size="11" fill="#666">{name}</text>')
# 阈值线
for t in (30, 55, 75):
    parts.append(f'<line x1="{ML}" y1="{Y(t)}" x2="{ML+PW}" y2="{Y(t)}" stroke="#999" stroke-dasharray="6 4" stroke-width="1"/>')
    parts.append(f'<text x="{ML-8}" y="{Y(t)+4}" text-anchor="end" font-size="11" fill="#666">{t}</text>')
# 基准权重线 w_r=30
parts.append(f'<line x1="{X(30)}" y1="{MT}" x2="{X(30)}" y2="{MT+PH}" stroke="#1a73e8" stroke-width="1.5"/>')
parts.append(f'<text x="{X(30)}" y="{MT+PH+20}" text-anchor="middle" font-size="11" fill="#1a73e8">w_r=30（基准）</text>')
# 坐标轴
parts.append(f'<line x1="{ML}" y1="{MT+PH}" x2="{ML+PW}" y2="{MT+PH}" stroke="#333"/>')
parts.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{MT+PH}" stroke="#333"/>')
for w in range(10, 51, 5):
    parts.append(f'<text x="{X(w)}" y="{MT+PH+20}" text-anchor="middle" font-size="10" fill="#666">{w}</text>')
    parts.append(f'<line x1="{X(w)}" y1="{MT+PH}" x2="{X(w)}" y2="{MT+PH+5}" stroke="#333"/>')
parts.append(f'<text x="{ML+PW/2}" y="{H-8}" text-anchor="middle" font-size="12">降雨权重 w_r（台风/地形按 40:30 比例分剩余，总和=100）</text>')
parts.append(f'<text x="16" y="{MT+PH/2}" text-anchor="middle" font-size="12" transform="rotate(-90 16 {MT+PH/2})">综合风险总分</text>')
# 图例（顶部横向）
lx = ML + 10
for i, sc in enumerate(data.keys()):
    col = COLORS[i % len(COLORS)]
    tx = lx + i * 128
    parts.append(f'<line x1="{tx}" y1="{MT-14}" x2="{tx+22}" y2="{MT-14}" stroke="{col}" stroke-width="2.5"/>')
    parts.append(f'<text x="{tx+26}" y="{MT-10}" font-size="11" fill="#333">{NAMES.get(sc, sc)}</text>')
# 曲线
for i, (sc, pts) in enumerate(data.items()):
    col = COLORS[i % len(COLORS)]
    d = "M " + " L ".join(f"{X(w):.1f} {Y(s):.1f}" for w, s, _ in pts)
    parts.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.5"/>')
parts.append('</svg>')
open("analysis/sensitivity.svg", "w", encoding="utf-8").write("\n".join(parts))
print("SVG written:", len("\n".join(parts)), "bytes")
