from __future__ import annotations

from threading import Lock

from app.core.errors import EngineBusyError


class ProcessLockService:
    def __init__(self) -> None:
        self._lock = Lock()

    def acquire(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise EngineBusyError("当前有任务正在处理，请稍后重试")

    def release(self) -> None:
        if self._lock.locked():
            self._lock.release()
