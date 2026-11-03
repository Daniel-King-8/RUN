"""上游接口常量。

与原项目 app/AppConfig.py 保持一致，仅做了环境变量覆盖，方便私有部署。
"""
import os

APPKEY = os.getenv("UNIRUN_APPKEY", "389885588s0648fa")
APPSECRET = os.getenv("UNIRUN_APPSECRET", "56E39A1658455588885690425C0FD16055A21676")
HOST = os.getenv("UNIRUN_HOST", "https://run-lb.tanmasports.com/")
if not HOST.endswith("/"):
    HOST += "/"

APPVERSION = "1.8.3"
BRAND = "iPhone"
DEVICETOKEN = ""
DEVICETYPE = "2"
MOBILETYPE = "iPhone 15 Pro Max"
SYSVERSION = "10"

CONTENTTYPE = "application/json; charset=UTF-8"
USERAGENT = "okhttp/3.12.0"

REQUEST_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "20"))

# 上游按本地时间校验 recordDate；容器默认 UTC，必须显式指定。
TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Shanghai")
