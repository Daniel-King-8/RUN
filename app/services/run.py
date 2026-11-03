"""跑步记录提交。

由原 app/requests/NewRunRecord.py + RunStandard.py 改造：
- token / 用户信息全部由调用方（会话）传入，不再读写 user_data.json；
- 所有上游请求都带超时；
- 错误以异常返回，由 Web 层统一处理。
"""
import datetime
import json
from zoneinfo import ZoneInfo

import requests

from app.auth import check_login_status
from app.config import (
    APPKEY,
    APPVERSION,
    BRAND,
    CONTENTTYPE,
    HOST,
    MOBILETYPE,
    REQUEST_TIMEOUT,
    SYSVERSION,
    TIMEZONE,
    USERAGENT,
)
from utils.sign import get_sign
from utils.track import gen_track_points

NOTICE = [
    "我认为这种事情是不可能的",
    "太快了",
    "要死了",
    "你正在自毁",
    "你正在自残",
    "你的锻炼正造成身体上的损伤",
    "六分是养身",
    "七分是自娱",
    "八分是治愈",
]


class RunError(Exception):
    """可展示给用户的业务错误。"""


class SessionExpired(RunError):
    """上游 token 失效，需要重新登录。"""


try:
    _TZ = ZoneInfo(TIMEZONE)
except Exception:  # 时区名无效时退回 UTC，避免整个服务起不来
    _TZ = datetime.timezone.utc


def _record_date() -> str:
    now = datetime.datetime.now(_TZ)
    return (now - datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")


def average_pace(distance_m: int, time_min: int) -> float:
    """返回分钟/公里。"""
    return time_min / distance_m * 1000


def _query_semester(token: str, school_id) -> str:
    if not check_login_status(token):
        raise SessionExpired("登录状态已失效，请重新登录")

    query = {"schoolId": school_id}
    headers = {
        "token": token,
        "appKey": APPKEY,
        "sign": get_sign(query, None),
        "Content-Type": CONTENTTYPE,
        "User-Agent": USERAGENT,
    }
    try:
        response = requests.get(
            HOST + "v1/unirun/query/runStandard",
            headers=headers,
            params=query,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RunError("查询跑步标准失败，请稍后重试") from exc

    if data.get("code") != 10000:
        raise RunError(data.get("msg") or "查询跑步标准失败")

    semester_year = (data.get("response") or {}).get("semesterYear")
    if not semester_year:
        raise RunError("跑步标准响应异常：缺少学期信息")
    return semester_year


def submit_run(
    *,
    distance_m: int,
    time_min: int,
    map_choice: str,
    token: str,
    user_id,
    student_name: str,
    school_id,
) -> str:
    pace = average_pace(distance_m, time_min)
    if pace < 6:
        index = min(int(pace), len(NOTICE) - 1)
        raise RunError(
            f"配速 {pace:.2f} 分钟/公里过快（{NOTICE[index]}），已停止提交"
        )

    if user_id in (None, "") or school_id in (None, ""):
        raise RunError("账号信息不完整，请重新登录后再试")

    semester_year = _query_semester(token, school_id)

    try:
        track_points = gen_track_points(distance_m, map_choice)
    except ValueError as exc:
        raise RunError(f"轨迹生成失败：{exc}") from exc

    body = {
        "againRunStatus": "0",
        "againRunTime": 0,
        "appVersions": APPVERSION,
        "brand": BRAND,
        "mobileType": MOBILETYPE,
        "sysVersions": SYSVERSION,
        "trackPoints": track_points,
        "distanceTimeStatus": "1",
        "innerSchool": "1",
        "runDistance": distance_m,
        "runTime": time_min,
        "userId": user_id,
        "vocalStatus": "1",
        "yearSemester": semester_year,
        "recordDate": _record_date(),
    }
    body_text = json.dumps(body)
    headers = {
        "token": token,
        "appKey": APPKEY,
        "sign": get_sign(None, body_text),
        "Content-Type": CONTENTTYPE,
        "User-Agent": USERAGENT,
    }

    try:
        response = requests.post(
            HOST + "v1/unirun/save/run/record/new",
            headers=headers,
            data=body_text,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RunError("提交跑步记录失败，请稍后重试") from exc

    if data.get("code") == 10000:
        result_desc = (data.get("response") or {}).get("resultDesc", "提交成功")
        return f"{student_name}: 配速 {pace:.2f} 分钟/公里，跑步结果：{result_desc}"

    message = data.get("msg") or "提交失败"
    if "登录" in message or "token" in message.lower():
        raise SessionExpired(message)
    raise RunError(message)
