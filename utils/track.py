"""按地图数据生成一条闭环跑步轨迹。

逻辑沿用原项目 utils/TrackUtil.py，增加了死循环与空 edge 的保护。
"""
import json
import random
import time

from geopy.distance import geodesic


class Location:
    def __init__(self, id, location, edge):
        self.id = id
        self.location = location
        self.edge = edge


def _rand_accuracy():
    return 10 * random.random()


def _calculate_distance(start, end):
    # 地图坐标为 "经度,纬度"，geopy 需要 (纬度, 经度)
    return geodesic((start[1], start[0]), (end[1], end[0])).meters


def _pick_next(current_location, last_index):
    edges = list(current_location.edge or [])
    if not edges:
        return None
    candidates = [e for e in edges if e != last_index]
    if not candidates:
        candidates = edges
    return random.choice(candidates)


def generate(distance_m, locations):
    """从随机点出发，沿 edge 链一直走到累计距离 >= distance_m。"""
    if not locations:
        raise ValueError("地图数据为空")

    by_id = {loc.id: loc for loc in locations}
    current_location = random.choice(locations)
    current_distance = 0.0
    result = []

    start_time = int(time.time() * 1000) - 30 * 60 * 1000
    lon, lat = current_location.location.split(",")
    result.append(f"{lon}-{lat}-{start_time}-{_rand_accuracy():.1f}")

    last_index = -1
    max_steps = 200000
    for _ in range(max_steps):
        if current_distance >= distance_m:
            break

        edge_index = _pick_next(current_location, last_index)
        if edge_index is None or edge_index not in by_id:
            break

        next_location = by_id[edge_index]
        start = current_location.location.split(",")
        end = next_location.location.split(",")
        start_data = list(map(float, start))
        end_data = list(map(float, end))

        go_distance = _calculate_distance(start_data, end_data)
        current_distance += go_distance

        start_time += go_distance / random.randint(1, 5) * 1000
        result.append(f"{end[0]}-{end[1]}-{start_time}-{_rand_accuracy():.1f}")

        last_index = current_location.id
        current_location = next_location
    else:
        raise ValueError("地图 edge 链过长，疑似存在环")

    start_time += random.randint(5, 10) * 1000
    replace = current_location.location.replace(",", "-")
    result.append(f"{replace}-{start_time}-{_rand_accuracy():.1f}")
    return json.dumps(result)


def gen_track_points(distance_m, map_choice):
    from app.services.mapdata import get_map_data

    data = get_map_data(map_choice)
    if not data:
        raise ValueError("未找到对应地图")
    locations = [Location(d["id"], d["location"], d["edge"]) for d in data]
    return generate(distance_m, locations)
