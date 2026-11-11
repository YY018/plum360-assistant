"""Request guard: keeps a public demo from exhausting the model API quota.

Four independent checks, all configured through environment variables:

* ``MAX_QUESTION_CHARS``   - reject very long questions (default 600)
* ``RATE_LIMIT_PER_HOUR``  - questions per client address per hour (default 30)
* ``DAILY_REQUEST_BUDGET`` - questions per day across all clients (default 400)
* ``DEMO_ACCESS_CODE``     - if set, clients must send it in ``X-Access-Code``

Counters live in memory, which is right for a single-process demo; set a value
to 0 to disable that check.
"""

from __future__ import annotations

import hmac
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field


class GuardError(Exception):
    def __init__(self, status: int, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.retry_after = retry_after


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass
class RequestGuard:
    max_question_chars: int = 600
    per_client_per_hour: int = 30
    daily_budget: int = 400
    access_code: str = ""
    _clients: dict[str, deque[float]] = field(default_factory=dict)
    _day: deque[float] = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def from_env(cls) -> "RequestGuard":
        return cls(
            max_question_chars=_int_env("MAX_QUESTION_CHARS", 600),
            per_client_per_hour=_int_env("RATE_LIMIT_PER_HOUR", 30),
            daily_budget=_int_env("DAILY_REQUEST_BUDGET", 400),
            access_code=os.getenv("DEMO_ACCESS_CODE", "").strip(),
        )

    def check_access(self, supplied_code: str | None) -> None:
        """Raise unless the access code matches (when one is configured)."""
        if not self.access_code:
            return
        if not supplied_code or not hmac.compare_digest(supplied_code.strip(), self.access_code):
            raise GuardError(
                401,
                "This demo needs an access code. Open the link you were given, or ask the "
                "project owner for one.",
            )

    def check_question(self, question: str) -> None:
        if self.max_question_chars and len(question) > self.max_question_chars:
            raise GuardError(
                413,
                f"Please keep questions under {self.max_question_chars} characters.",
            )

    def reserve(self, client_id: str, now: float | None = None) -> None:
        """Count one model-backed request for this client, or raise 429."""
        now = time.time() if now is None else now
        with self._lock:
            if self.daily_budget:
                self._trim(self._day, now - 86400)
                if len(self._day) >= self.daily_budget:
                    oldest = self._day[0]
                    raise GuardError(
                        429,
                        "The demo has reached its daily question limit. Please try again "
                        "tomorrow.",
                        retry_after=max(1, int(oldest + 86400 - now)),
                    )
            if self.per_client_per_hour:
                window = self._clients.setdefault(client_id, deque())
                self._trim(window, now - 3600)
                if len(window) >= self.per_client_per_hour:
                    raise GuardError(
                        429,
                        f"You have asked {self.per_client_per_hour} questions in the last "
                        "hour, which is the demo's limit. Please try again a little later.",
                        retry_after=max(1, int(window[0] + 3600 - now)),
                    )
                window.append(now)
            if self.daily_budget:
                self._day.append(now)
            # Forget idle clients so memory stays bounded.
            if len(self._clients) > 5000:
                for key in [k for k, v in self._clients.items() if not v or v[-1] < now - 3600]:
                    del self._clients[key]

    def status(self) -> dict[str, int | bool]:
        now = time.time()
        with self._lock:
            self._trim(self._day, now - 86400)
            used = len(self._day)
        return {
            "daily_budget": self.daily_budget,
            "used_today": used,
            "per_client_per_hour": self.per_client_per_hour,
            "max_question_chars": self.max_question_chars,
            "access_code_required": bool(self.access_code),
        }

    @staticmethod
    def _trim(window: deque[float], cutoff: float) -> None:
        while window and window[0] < cutoff:
            window.popleft()
