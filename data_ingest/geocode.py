"""地理编码兜底：内置小区匹配不上时，把任意地址解析为经纬度。

主用 Nominatim（OpenStreetMap，中文地址覆盖好，无需 key，遵守 1次/秒 限速），
Open-Meteo 地理编码作备选。失败返回 None，调用方再决定降级。
只用标准库 urllib。
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

_UA = "typhoonready/1.0 (AI4Climate demo; contact: via GitHub repo)"


def _get(url: str, timeout: int = 20) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _nominatim(address: str) -> dict | None:
    url = ("https://nominatim.openstreetmap.org/search?q="
           + urllib.parse.quote(address)
           + "&format=json&limit=1&accept-language=zh")
    data = _get(url) or []
    if not data:
        return None
    r = data[0]
    disp = r.get("display_name", "")
    # 取 display_name 里靠前的中文地名片段作展示名
    name = disp.split(",")[0].strip() or address
    return {"name": name, "lat": float(r["lat"]), "lon": float(r["lon"]),
            "admin": "", "display": disp}


def _open_meteo(address: str) -> dict | None:
    url = ("https://geocoding-api.open-meteo.com/v1/search?name="
           + urllib.parse.quote(address) + "&count=1&language=zh&format=json")
    data = _get(url) or {}
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    admin = "，".join(x for x in [r.get("admin1"), r.get("admin2")] if x)
    return {"name": r.get("name", address), "lat": r["latitude"],
            "lon": r["longitude"], "admin": admin, "display": ""}


def _variants(address: str) -> list[str]:
    """查询变体：完整地址 -> 前3字 -> 前2字（城市级兜底）。"""
    v = [address]
    if len(address) > 3:
        v.append(address[:3])
    if len(address) > 2:
        v.append(address[:2])
    return v


def geocode(address: str, timeout: int = 20) -> dict | None:
    """返回 {"name", "lat", "lon", "admin"}，失败返回 None。"""
    for q in _variants(address):
        try:
            r = _nominatim(q)
            if r:
                return r
        except Exception:
            pass
        time.sleep(1.1)  # Nominatim 限速要求
    for q in _variants(address):
        try:
            r = _open_meteo(q)
            if r:
                return r
        except Exception:
            pass
    return None
