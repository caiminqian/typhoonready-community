"""地形内涝风险底图：小区粒度的内涝风险等级（0-3 级）+ 高程 + 历史内涝记录。

真实源（待接入）：城市内涝风险区划图 / DEM 高程。
当前为内置示例底图（data/mock/flood_zones.json），评审离线可查。
"""
import json
from pathlib import Path

from .base import MOCK_DIR


def list_communities() -> list[dict]:
    """返回内置示例小区列表。"""
    path = MOCK_DIR / "communities.json"
    return json.loads(path.read_text(encoding="utf-8"))["communities"]


def find_community(address: str) -> dict | None:
    """按地址关键字模糊匹配小区；匹配不上返回 None。"""
    for c in list_communities():
        if c["name"] in address or address in c["name"] or c["id"] in address:
            return c
    # 再试地址片段匹配
    for c in list_communities():
        key = c["name"].replace("小区", "")
        if key and key in address:
            return c
    return None


def get_flood_zone(community_id: str) -> dict:
    """取某小区的内涝风险底图记录。"""
    path = MOCK_DIR / "flood_zones.json"
    zones = json.loads(path.read_text(encoding="utf-8"))["zones"]
    return zones.get(community_id, {"zone_level": 1, "elevation_m": 5.0, "history": "暂无历史内涝记录"})
