"""全链路编排：地址 -> 数据接入 -> 风险评分 -> 指引生成。

run_demo.py 和 app/main.py 都调这里，保证 CLI 与 Web 走同一条链路。

两种运行模式：
- live（默认）：实时台风（失败回退 mock）+ 未来 3 天降雨预报
- replay：历史复盘（贝碧嘉 2024 真实路径 + ERA5 再分析降水），
  用于"当时若有本系统"的复盘演示。调用：
  run_pipeline("书院社区", typhoon_mode="replay", replay_case="bebinca",
               rain_start="2024-09-14", rain_end="2024-09-17")
"""
from __future__ import annotations

from data_ingest.rainfall import RainfallFetcher
from data_ingest import terrain
from data_ingest.geocode import geocode
from data_ingest.typhoon import TyphoonFetcher
from guidance.generator import generate
from risk_engine.scorer import assess, haversine_km


def run_pipeline(address: str, typhoon_mode: str = "live",
                 replay_case: str | None = None,
                 rain_start: str | None = None,
                 rain_end: str | None = None) -> dict:
    """输入地址（小区名关键字），输出完整评估结果。"""
    community = terrain.find_community(address)
    terrain_source = "mock"
    if community is None:
        # 兜底：任意地址走地理编码，内涝底图用默认估计值并如实标注
        geo = geocode(address)
        if geo is None:
            supported = [c["name"] for c in terrain.list_communities()]
            raise ValueError(f"无法定位：{address}；可试示例小区：{supported}")
        community = {
            "id": f"geo-{geo['lat']:.2f}-{geo['lon']:.2f}",
            "name": f"{geo['name']}（{geo['admin']}）" if geo["admin"] else geo["name"],
            "address": address, "lat": geo["lat"], "lon": geo["lon"],
        }
        terrain_source = "estimated"

    # 1) 数据接入（真实接口优先，失败自动回退 mock；台风与降雨并行拉取）
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_typhoon = pool.submit(TyphoonFetcher().fetch, mode=typhoon_mode,
                                  case=replay_case)
        fut_rain = pool.submit(
            RainfallFetcher().fetch, lat=community["lat"], lon=community["lon"],
            start_date=rain_start, end_date=rain_end)
        typhoon = fut_typhoon.result()
        rainfall = fut_rain.result()
    zone = terrain.get_flood_zone(community["id"])
    if terrain_source == "estimated":
        zone = {"zone_level": 1, "elevation_m": 5.0,
                "history": "该地址无内置内涝底图，地形分按默认估计值计算，仅供参考"}

    # 2) 复合风险评分
    risk = assess(typhoon.data, rainfall.data, zone, community["lat"], community["lon"])

    # 3) 指引生成需要的上下文
    points = typhoon.data.get("points", [])
    dists = [haversine_km(community["lat"], community["lon"], p["lat"], p["lon"]) for p in points]
    context = {
        "min_dist_km": min(dists) if dists else 9999,
        "max_wind_ms": max((p.get("wind_ms") or 0 for p in points), default=0),
        "max_rain_mm": max((d.get("mm_24h", 0) for d in rainfall.data.get("daily", [])), default=0),
    }

    # 4) AI 指引（有 key 走 LLM，无 key 走模板降级）
    guidance = generate(risk, community, zone, context)

    return {
        "community": community,
        "risk": risk,
        "guidance": guidance,
        "mode": typhoon_mode,
        "data_sources": {
            "typhoon": typhoon.source,
            "rainfall": rainfall.source,
            "terrain": terrain_source,
        },
        "data_notes": [n for n in (typhoon.note, rainfall.note) if n],
    }
