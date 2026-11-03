"""地图注册表。

新增学校：把地图文件放进 app/maps/ 下，然后在这里注册 key 与显示名称。
"""
from app.maps.cuit.hkg import hkg
from app.maps.cuit.lqy import lqy
from app.maps.cdutcm.wj import wj

MAPS = {
    "cuit_hkg": {"name": "成都信息工程大学（航空港校区）", "loader": hkg},
    "cuit_lqy": {"name": "成都信息工程大学（龙泉校区）", "loader": lqy},
    "cdutcm_wj": {"name": "成都中医药大学（温江校区）", "loader": wj},
}


def list_maps():
    return [{"key": key, "name": item["name"]} for key, item in MAPS.items()]


def get_map_data(map_key):
    item = MAPS.get(map_key)
    if item is None:
        return None
    return item["loader"]()
