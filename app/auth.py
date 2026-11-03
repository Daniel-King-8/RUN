"""上游登录与 token 校验。

注意：密码只在 login() 的调用栈中使用一次，不写日志、不写文件、不放入 Session。
"""
import json

import requests

from app.config import (
    APPKEY,
    APPVERSION,
    BRAND,
    CONTENTTYPE,
    DEVICETOKEN,
    DEVICETYPE,
    HOST,
    MOBILETYPE,
    REQUEST_TIMEOUT,
    SYSVERSION,
    USERAGENT,
)
from utils.md5 import string_to_md5
from utils.sign import get_sign


class AuthError(Exception):
    pass


def login(phone: str, password: str) -> tuple[str, dict]:
    """返回 (token, profile)。失败抛 AuthError，错误信息可直接展示给用户。"""
    body = {
        "appVersion": APPVERSION,
        "brand": BRAND,
        "deviceToken": DEVICETOKEN,
        "deviceType": DEVICETYPE,
        "mobileType": MOBILETYPE,
        "password": string_to_md5(password),
        "sysVersion": SYSVERSION,
        "userPhone": phone,
    }
    body_text = json.dumps(body)
    headers = {
        "appKey": APPKEY,
        "sign": get_sign(None, body_text),
        "Content-Type": CONTENTTYPE,
        "User-Agent": USERAGENT,
    }

    try:
        response = requests.post(
            HOST + "v1/auth/login/password",
            headers=headers,
            data=body_text,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise AuthError("无法连接登录服务，请稍后重试") from exc

    if data.get("code") != 10000:
        raise AuthError(data.get("msg") or "登录失败，请检查手机号和密码")

    payload = data.get("response") or {}
    token = (payload.get("oauthToken") or {}).get("token")
    if not token:
        raise AuthError("登录响应异常：缺少 token")

    profile = {key: value for key, value in payload.items() if key != "oauthToken"}
    return token, profile


def check_login_status(token: str) -> bool:
    headers = {
        "token": token,
        "appKey": APPKEY,
        "sign": get_sign(None, None),
        "Content-Type": CONTENTTYPE,
        "User-Agent": USERAGENT,
    }
    try:
        response = requests.get(
            HOST + "v1/auth/query/token",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return False
    return data.get("code") == 10000
