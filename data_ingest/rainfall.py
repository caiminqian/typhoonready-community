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

UA = {"User-Agent": "typhoonready/1.0 (AI4Climate demo; contact: via GitHub typhoonready-community)"}

# 进程内缓存：同一坐标（0.1° 网格）3 小时内复用，应对免费接口按 IP 限流
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3 * 3600


def _get_json(url: str, retries: int = 2) -> dict:
    import time
    import urllib.error
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429 and attempt < retries - 1:
                # 尊重 Retry-After（最多等 10 秒），否则指数退避
                wait = e.headers.get("Retry-After")
                try:
                    delay = min(float(wait), 10) if wait else 2 * (attempt + 1)
                except ValueError:
                    delay = 2 * (attempt + 1)
                time.sleep(delay)
                continue
            raise
    raise last


def _cache_key(lat: float, lon: float, start: str | None, end: str | None) -> str:
    return f"{round(lat, 1)},{round(lon, 1)},{start or ''},{end or ''}"


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
        import time
        lat = kwargs.get("lat")
        lon = kwargs.get("lon")
        if lat is None or lon is None:
            raise RuntimeError("缺少经纬度参数")
        start = kwargs.get("start_date")
        end = kwargs.get("end_date")
        key = _cache_key(lat, lon, start, end)
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            data = dict(hit[1])
            data["note"] += "（3 小时内缓存）"
            return data
        if start and end:
            data = self._fetch_archive(lat, lon, start, end)
        else:
            data = self._fetch_forecast(lat, lon)
        _CACHE[key] = (time.time(), data)
        return data

    def _fetch_forecast(self, lat: float, lon: float) -> dict:
        try:
            return self._fetch_open_meteo(lat, lon)
        except Exception as e:
            # Open-Meteo 被限流（共享 IP 常见）时切 7timer 备用源，保证各地有真数
            try:
                return self._fetch_7timer(lat, lon)
            except Exception:
                raise e

    def _fetch_open_meteo(self, lat: float, lon: float) -> dict:
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

    def _fetch_7timer(self, lat: float, lon: float) -> dict:
        # 7timer 免费无 key；prec_amount 为每 3 小时降水量（毫米），聚合成逐日
        from datetime import datetime
        url = (f"http://www.7timer.info/bin/api.pl?lon={lon:.2f}&lat={lat:.2f}"
               f"&product=civil&output=json")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as resp:
            # 7timer 会 302 跳转，urllib 默认跟随
            raw = json.loads(resp.read().decode("utf-8"))
        series = raw.get("dataseries", [])
        if not series:
            raise RuntimeError("7timer 返回为空")
        init = datetime.strptime(raw.get("init", ""), "%Y%m%d%H")
        per_day: dict[str, float] = {}
        for p in series[:24]:  # 未来 72 小时
            dt = init + timedelta(hours=p.get("timepoint", 0))
            day = dt.strftime("%Y-%m-%d")
            per_day[day] = per_day.get(day, 0.0) + float(p.get("prec_amount", 0) or 0)
        daily = [{"date": d, "mm_24h": round(v, 1)}
                 for d, v in sorted(per_day.items())[:3]]  # 与 Open-Meteo 对齐：未来 3 天
        return self._wrap(lat, lon, daily, "live：7timer 逐 3 小时降水聚合（Open-Meteo 限流时备用）")

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
