"""台风路径接入。

三种模式：
- live（默认）：尝试解析中央气象台台风网实时页面，失败自动回退 mock。
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

    def _fetch_live(self, **kwargs) -> dict:
        # 中央气象台台风网为 HTML 页面（无官方 JSON），报文需正则提取；
        # 实时解析 fragile，赛前如无稳定方案则保持回退 mock。
        # 预留：NMC https://www.nmc.cn/publish/typhoon/message.html
        raise RuntimeError("实时台风路径解析尚未接入")
