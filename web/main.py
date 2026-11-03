"""RUN Web 服务入口。

安全模型：
- 账号密码只在 POST /api/login 的请求生命周期内使用，不落盘、不写日志；
- 上游 token 只存在当前进程的会话对象里，浏览器只拿到一个随机 session cookie；
- 提交任务结束（无论成功失败）、主动登出、空闲超时都会销毁会话；
- 默认单 worker 运行，因此会话不会跨进程；进程重启 = 全部登出。

公网暴露不在支持范围内。默认请保持 compose 中 127.0.0.1 的端口绑定，
或放在带认证的反向代理之后。
"""
from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import AuthError, login as upstream_login
from app.services.mapdata import MAPS, list_maps
from app.services.run import RunError, SessionExpired, submit_run
from app.session import Session, SessionStore

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
COOKIE_NAME = "unirun_sid"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


SESSION_IDLE_TTL = _int_env("SESSION_IDLE_TTL", 900)
SESSION_MAX_TTL = _int_env("SESSION_MAX_TTL", 7200)
SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
ACCESS_CODE = os.getenv("ACCESS_CODE", "")
LOGIN_MAX_ATTEMPTS = _int_env("LOGIN_MAX_ATTEMPTS", 10)
LOGIN_WINDOW_SECONDS = _int_env("LOGIN_WINDOW_SECONDS", 300)

store = SessionStore(idle_ttl=SESSION_IDLE_TTL, max_ttl=SESSION_MAX_TTL)


class AttemptLimiter:
    """极简内存限流，按客户端 IP 统计登录尝试。"""

    def __init__(self, max_attempts: int, window: int):
        self.max_attempts = max_attempts
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits[key] if now - t < self.window]
            if len(hits) >= self.max_attempts:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


limiter = AttemptLimiter(LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.start_sweeper()
    yield
    store.stop_sweeper()


app = FastAPI(
    title="RUN Web",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


class LoginRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    access_code: str | None = Field(default=None, max_length=128)


class RunRequest(BaseModel):
    distance: int = Field(ge=1, le=5000)
    time: int = Field(ge=30, le=100)
    map: str = Field(min_length=1, max_length=64)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    if urlparse(origin).netloc != request.headers.get("host", ""):
        raise HTTPException(status_code=403, detail="跨站请求被拒绝")


def _public_profile(profile: dict) -> dict:
    return {
        "studentName": profile.get("studentName") or "",
        "studentId": profile.get("studentId") or "",
        "schoolName": profile.get("schoolName") or "",
    }


def require_session(request: Request) -> Session:
    session = store.get(request.cookies.get(COOKIE_NAME, ""))
    if session is None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return session


def _set_session_cookie(response: JSONResponse, sid: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=sid,
        max_age=SESSION_MAX_TTL,
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
        path="/",
    )


def _clear_session_cookie(response: JSONResponse) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return JSONResponse(status_code=204, content=None)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/config")
def api_config():
    return {
        "access_code_required": bool(ACCESS_CODE),
        "maps": list_maps(),
        "distance": {"min": 1, "max": 5000, "default": 4999},
        "time": {"min": 30, "max": 100, "default": 59},
        "session_idle_ttl": SESSION_IDLE_TTL,
    }


@app.post("/api/login")
def api_login(payload: LoginRequest, request: Request):
    _same_origin(request)

    if not limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="尝试过于频繁，请稍后再试")

    if ACCESS_CODE and not secrets.compare_digest(payload.access_code or "", ACCESS_CODE):
        raise HTTPException(status_code=403, detail="访问口令不正确")

    try:
        token, profile = upstream_login(payload.phone, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    session = store.create(token, profile)
    response = JSONResponse({"ok": True, "profile": _public_profile(profile)})
    _set_session_cookie(response, session.sid)
    return response


@app.get("/api/me")
def api_me(session: Session = Depends(require_session)):
    return {"ok": True, "profile": _public_profile(session.profile)}


@app.post("/api/logout")
def api_logout(request: Request, session: Session = Depends(require_session)):
    _same_origin(request)
    store.destroy(session.sid)
    response = JSONResponse({"ok": True, "logged_out": True})
    _clear_session_cookie(response)
    return response


@app.post("/api/run")
def api_run(payload: RunRequest, request: Request, session: Session = Depends(require_session)):
    _same_origin(request)

    if payload.map not in MAPS:
        raise HTTPException(status_code=400, detail="地图不存在")

    if not session.lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="已有提交任务正在执行")

    session.busy = True
    try:
        result = submit_run(
            distance_m=payload.distance,
            time_min=payload.time,
            map_choice=payload.map,
            token=session.token,
            user_id=session.profile.get("userId"),
            student_name=session.profile.get("studentName") or "同学",
            school_id=session.profile.get("schoolId"),
        )
        body = {"ok": True, "result": result, "logged_out": True}
    except SessionExpired as exc:
        body = {"ok": False, "error": str(exc), "logged_out": True}
    except RunError as exc:
        body = {"ok": False, "error": str(exc), "logged_out": True}
    except Exception:
        body = {"ok": False, "error": "提交时发生未知错误，请稍后重试", "logged_out": True}
    finally:
        session.busy = False
        session.lock.release()
        # 一次使用结束，无论结果如何都销毁会话与 token
        store.destroy(session.sid)

    response = JSONResponse(body)
    _clear_session_cookie(response)
    return response


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
