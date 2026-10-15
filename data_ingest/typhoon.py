"""台风路径接入。

三种模式：
- live（默认）：中央气象台台风网 JSON 接口（typhoon.nmc.cn，
  含实况路径 + BABJ 官方预报路径）；无活跃台风或接口不可用时回退 mock。
- replay：历史复盘模式，加载 data/real/ 下的真实最佳路径
  （如贝碧嘉 2024，IBTrACS v04r01 / JMA 列），用于"当时若有本系统"的复盘演示。
- mock：内置模拟台风（72 小时逼近浙闽沿海），保证离线可跑。

points 统一 schema：[{time, lat, lon, wind_ms, pressure_hpa}]
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import MOCK_DIR, BaseFetcher

REAL_DIR = MOCK_DIR.parent / "real"

# 复盘案例注册表：key -> 文件名
REPLAY_CASES = {
    "bebinca": "bebinca_2024_track.json",
}


class TyphoonFetcher(BaseFetcher):
    mock_file = "typhoon_track.json"

    def fetch(self, mode: str = "live", **kwargs):
        """mode: live / replay / mock。replay 需 kwargs['case']='bebinca'。"""
        if mode == "replay":
            return self._fetch_replay(kwargs.get("case", "bebinca"))
        if mode == "mock":
            return self._mock_result("指定 mock 模式")
        return super().fetch(**kwargs)

    def _fetch_replay(self, case: str):
        from .base import FetchResult
        fname = REPLAY_CASES.get(case)
        if not fname:
            raise RuntimeError(f"未知复盘案例：{case}，可选：{list(REPLAY_CASES)}")
        path = REAL_DIR / fname
        data = json.loads(path.read_text(encoding="utf-8"))
        return FetchResult(data=data, source="replay",
                           note=f"历史复盘：{data.get('name')}（{data.get('source')}）")

    def _mock_result(self, why: str):
        from .base import FetchResult
        return FetchResult(data=self._load_mock(), source="mock", note=why)

    # 中央气象台台风网 JSON 接口（其官网前端自用，半公开）
    _LIST_URL = "http://typhoon.nmc.cn/weatherservice/typhoon/jsons/list_default"
    _VIEW_URL = "http://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_{tid}"
    _UA = {"User-Agent": "typhoonready/1.0"}

    def _fetch_live(self, **kwargs) -> dict:
        import re
        import urllib.request

        def get_jsonp(url: str) -> dict:
            # 注：list 接口返回双括号 JSONP：typhoon_jsons_list_default(({...}))
            req = urllib.request.Request(url, headers=self._UA)
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8").strip()
            # 双括号 JSONP：typhoon_jsons_list_default(({...}))，直接定位花括号
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                raise RuntimeError("JSONP 解析失败")
            return json.loads(raw[start:end + 1])

        data = get_jsonp(self._LIST_URL)
        active = [t for t in data.get("typhoonList", []) if t[7] == "start"]
        if not active:
            raise RuntimeError("当前西北太平洋无活跃台风")
        # 取第一个活跃台风（通常即编号最新/最受关注的一个）
        tid, eng, cn = active[0][0], active[0][1], active[0][2]
        view = get_jsonp(self._VIEW_URL.format(tid=tid))
        tp = view["typhoon"]
        name = f"台风{cn}（{eng}）"
        points = []
        for h in tp[8]:  # 实况路径：[id, 时间, ts, 等级, lon, lat, 气压, 风速m/s, ...]
            points.append({"time": h[1], "lat": h[5], "lon": h[4],
                           "wind_ms": h[7], "pressure_hpa": h[6],
                           "kind": "observed"})
        # BABJ（中央气象台）官方预报路径拼在后面
        if tp[8]:
            fc = tp[8][-1][11].get("BABJ", [])
            for f in fc:  # [提前小时, 时间, lon, lat, 气压, 风速, 来源]
                points.append({"time": f[1], "lat": f[3], "lon": f[2],
                               "wind_ms": f[5], "pressure_hpa": f[4],
                               "kind": "forecast"})
        if not points:
            raise RuntimeError("台风路径数据为空")
        return {"name": name, "source": "中央气象台台风网实时",
                "points": points, "status": "active"}
