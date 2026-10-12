"""Límite de intentos de login fallidos (ventana deslizante, en memoria).

Sirve para un solo proceso. Con varios workers/servidores usar Redis o un
límite en el proxy (NGINX) además de este.
"""
import threading
import time
from collections import defaultdict, deque

from core.config import settings
from core.errors import TooManyRequestsError


class LoginRateLimiter:
    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        window = settings.login_window_seconds
        q = self._failures[key]
        while q and now - q[0] > window:
            q.popleft()
        return q

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, now)
            if len(q) >= settings.login_max_attempts:
                retry = max(1, int(settings.login_window_seconds - (now - q[0])))
                raise TooManyRequestsError(
                    f"Demasiados intentos fallidos. Probá de nuevo en {retry} segundos.",
                    headers={"Retry-After": str(retry)},
                )

    def register_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_limiter = LoginRateLimiter()
