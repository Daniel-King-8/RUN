"""地图注册表与账号校区匹配。

每个地图可以配置：
- school_ids: 上游 schoolId，命中后直接锁定该学校的地图；
- school_keywords: schoolName 中包含的关键词，作为 schoolId 缺失时的兜底；
- campus_keywords: 校区关键词，用于同一学校多校区时进一步筛选。
"""
from app.maps.cuit.hkg import hkg
from app.maps.cuit.lqy import lqy
from app.maps.cdutcm.wj import wj
from app.maps.scyz.jk import scyz_jk

MAPS = {
    "cuit_hkg": {
        "name": "成都信息工程大学（航空港校区）",
        "loader": hkg,
        "school_ids": (),
        "school_keywords": ("成都信息工程大学", "成信大"),
        "campus_keywords": ("航空港",),
    },
    "cuit_lqy": {
        "name": "成都信息工程大学（龙泉校区）",
        "loader": lqy,
        "school_ids": (),
        "school_keywords": ("成都信息工程大学", "成信大"),
        "campus_keywords": ("龙泉",),
    },
    "cdutcm_wj": {
        "name": "成都中医药大学（温江校区）",
        "loader": wj,
        "school_ids": (),
        "school_keywords": ("成都中医药大学", "成中医"),
        "campus_keywords": ("温江",),
    },
    "scyz_jk": {
        "name": "四川邮电职业技术学院",
        "loader": scyz_jk,
        "school_ids": (2922,),
        "school_keywords": ("四川邮电职业技术学院", "四川邮电"),
        "campus_keywords": (),
    },
}


def list_maps():
    return [{"key": key, "name": item["name"]} for key, item in MAPS.items()]


def get_map_data(map_key):
    item = MAPS.get(map_key)
    if item is None:
        return None
    return item["loader"]()


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_map_keys(profile):
    """返回 (map_key 列表, 是否按账号匹配成功)。"""
    school_id = _as_int(profile.get("schoolId"))
    school_name = str(profile.get("schoolName") or "")
    context = " ".join(
        str(profile.get(key) or "")
        for key in ("schoolName", "collegeName", "className")
    )

    keys = []
    if school_id is not None:
        keys = [key for key, item in MAPS.items() if school_id in item["school_ids"]]

    if not keys:
        keys = [
            key
            for key, item in MAPS.items()
            if any(word in school_name for word in item["school_keywords"])
        ]

    matched = bool(keys)
    if keys:
        campus_hits = [
            key
            for key in keys
            if any(word in context for word in MAPS[key]["campus_keywords"])
        ]
        if campus_hits:
            keys = campus_hits
    else:
        # 没有匹配到学校时退回全部地图，避免账号无法使用
        keys = list(MAPS)

    return keys, matched


def map_payload(profile):
    keys, matched = resolve_map_keys(profile)
    return {
        "maps": [{"key": key, "name": MAPS[key]["name"]} for key in keys],
        "default_map": keys[0] if keys else None,
        "map_matched": matched,
    }
