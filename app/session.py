"""进程内会话存储。

设计约束（与 README 的安全说明一致）：
- 只存内存，不落盘、不写日志；
- 每个浏览器会话一个独立 Session，token 互不可见；
- 空闲超时 / 绝对超时 / 主动登出都会立即销毁 token；
- 进程重启即全部失效，这是预期行为。
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Session:
    sid: str
    token: str = field(repr=False)
    profile: dict
    created_at: float
    last_seen: float
    busy: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class SessionStore:
    def __init__(self, idle_ttl: int = 900, max_ttl: int = 7200):
        self.idle_ttl = idle_ttl
        self.max_ttl = max_ttl
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.RLock()
        self._sweeper: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def create(self, token: str, profile: dict) -> Session:
        now = time.time()
        session = Session(
            sid=secrets.token_urlsafe(32),
            token=token,
            profile=profile,
            created_at=now,
            last_seen=now,
        )
        with self._lock:
            self._sessions[session.sid] = session
        return session

    def get(self, sid: str, touch: bool = True) -> Optional[Session]:
        if not sid:
            return None
        now = time.time()
        with self._lock:
            session = self._sessions.get(sid)
            if session is None:
                return None
            if self._expired(session, now):
                self._sessions.pop(sid, None)
                return None
            if touch:
                session.last_seen = now
            return session

    def destroy(self, sid: str) -> None:
        with self._lock:
            self._sessions.pop(sid, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _expired(self, session: Session, now: float) -> bool:
        if now - session.last_seen > self.idle_ttl:
            return True
        if now - session.created_at > self.max_ttl:
            return True
        return False

    def sweep(self) -> None:
        now = time.time()
        with self._lock:
            dead = [
                sid
                for sid, s in self._sessions.items()
                if not s.busy and self._expired(s, now)
            ]
            for sid in dead:
                self._sessions.pop(sid, None)

    def start_sweeper(self) -> None:
        if self._sweeper is not None:
            return
        self._stop.clear()

        def loop():
            while not self._stop.wait(30):
                self.sweep()

        self._sweeper = threading.Thread(target=loop, name="session-sweeper", daemon=True)
        self._sweeper.start()

    def stop_sweeper(self) -> None:
        self._stop.set()
        self._sweeper = None
