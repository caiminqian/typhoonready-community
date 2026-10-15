"""降雨预报接入。

真实源：Open-Meteo（免 key）
- 未来预报：api.open-meteo.com/v1/forecast（未来 3 天逐日降水）
- 历史复盘：archive-api.open-meteo.com/v1/archive（ERA5 再分析逐小时降水，
  按 start_date/end_date 聚合成逐日），用于与台风复盘案例对齐。
失败时自动回退 mock（台风影响情景）。
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

from .base import BaseFetcher

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI4Climate-Demo"}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


class RainfallFetcher(BaseFetcher):
    mock_file = "rainfall_forecast.json"

    def fetch(self, **kwargs):
        """archive（历史复盘）模式成功时 source 标 replay，诚实区分数据性质。"""
        try:
            data = self._fetch_live(**kwargs)
            src = "replay" if (kwargs.get("start_date") and kwargs.get("end_date")) else "live"
            from .base import FetchResult
            return FetchResult(data=data, source=src)
        except Exception as e:
            data = self._load_mock()
            from .base import FetchResult
            return FetchResult(data=data, source="mock",
                               note=f"真实接口不可用（{e}），已回退内置 mock 数据")

    def _fetch_live(self, **kwargs) -> dict:
        lat = kwargs.get("lat")
        lon = kwargs.get("lon")
        if lat is None or lon is None:
            raise RuntimeError("缺少经纬度参数")
        start = kwargs.get("start_date")
        end = kwargs.get("end_date")
        if start and end:
            return self._fetch_archive(lat, lon, start, end)
        return self._fetch_forecast(lat, lon)

    def _fetch_forecast(self, lat: float, lon: float) -> dict:
        q = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon,
            "daily": "precipitation_sum",
            "timezone": "Asia/Shanghai", "forecast_days": 3,
        })
        raw = _get_json("https://api.open-meteo.com/v1/forecast?" + q)
        d = raw.get("daily", {})
        daily = [{"date": dt, "mm_24h": round(float(s or 0), 1)}
                 for dt, s in zip(d.get("time", []), d.get("precipitation_sum", []))]
        if not daily:
            raise RuntimeError("Open-Meteo forecast 返回为空")
        return self._wrap(lat, lon, daily, "live：Open-Meteo 逐日降水预报（未来3天）")

    def _fetch_archive(self, lat: float, lon: float, start: str, end: str) -> dict:
        q = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon,
            "start_date": start, "end_date": end,
            "hourly": "precipitation", "timezone": "Asia/Shanghai",
        })
        raw = _get_json("https://archive-api.open-meteo.com/v1/archive?" + q)
        h = raw.get("hourly", {})
        times = h.get("time", [])
        vals = h.get("precipitation", [])
        per_day: dict[str, float] = {}
        for t, v in zip(times, vals):
            day = t[:10]
            per_day[day] = per_day.get(day, 0.0) + float(v or 0)
        daily = [{"date": d, "mm_24h": round(s, 1)} for d, s in sorted(per_day.items())]
        if not daily:
            raise RuntimeError("Open-Meteo archive 返回为空")
        return self._wrap(lat, lon, daily,
                          f"replay：Open-Meteo ERA5 再分析降水（{start}~{end}）")

    @staticmethod
    def _wrap(lat, lon, daily, note):
        now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        return {"location": f"{lat:.3f},{lon:.3f}", "updated": now,
                "daily": daily, "note": note}
