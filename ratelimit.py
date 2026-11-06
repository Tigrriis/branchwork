"""How often one visitor may try to sign in, sign up, or ask for a
confirmation email.

A sliding window per key, held in memory. Each gunicorn worker keeps its own
counts, so with two workers a visitor can get up to twice the stated limit
before every worker has refused them. That is fine for slowing bots and
password guessing, and it needs no Redis. If the app ever runs on more
instances, move this to Render Key Value.

Three kinds of key:

* An IP address, which bounds how hard one machine can hammer a form. Behind
  Render's proxies, the address is read from the headers the edge sets. A
  client can forge those headers, which only helps it dodge its own limit, so
  per-IP limits are generous.
* An email address, which counts failed sign-ins whatever IP they come from.
  This is the part that stops password guessing, and it cannot be dodged.
* An account, which counts the confirmation emails it asks for, so nobody
  can use the "send it again" button to flood an inbox.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from flask import current_app, request

# (limit, window in seconds)
LOGIN_PER_IP = (30, 15 * 60)
LOGIN_FAILS_PER_EMAIL = (10, 15 * 60)
REGISTER_PER_IP = (10, 60 * 60)
# Asking for another email confirmation link, per account.
VERIFY_SEND_PER_USER = (5, 60 * 60)

_SWEEP_EVERY = 60.0


class Limiter:
    def __init__(self) -> None:
        self._hits: dict[tuple, deque] = {}
        self._lock = threading.Lock()
        self._swept = time.monotonic()

    def _recent(self, key: tuple, window: float, now: float) -> deque:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window:
            hits.popleft()
        return hits

    def _sweep(self, now: float) -> None:
        """Drop keys with nothing recent, so memory stays bounded."""
        if now - self._swept < _SWEEP_EVERY:
            return
        self._swept = now
        longest = max(w for _, w in (LOGIN_PER_IP, LOGIN_FAILS_PER_EMAIL, REGISTER_PER_IP,
                                     VERIFY_SEND_PER_USER))
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - longest]:
            del self._hits[key]

    def blocked(self, key: tuple, rule: tuple[int, int]) -> bool:
        """Has this key used up its allowance? Records nothing."""
        limit, window = rule
        now = time.monotonic()
        with self._lock:
            return len(self._recent(key, window, now)) >= limit

    def hit(self, key: tuple, rule: tuple[int, int]) -> bool:
        """Count one attempt. True if it went over the limit."""
        limit, window = rule
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            hits = self._recent(key, window, now)
            if len(hits) >= limit:
                return True
            hits.append(now)
            return False

    def clear(self, key: tuple) -> None:
        with self._lock:
            self._hits.pop(key, None)


def limiter() -> Limiter | None:
    """This app's limiter, or None when limits are switched off."""
    if not current_app.config.get("RATELIMIT_ENABLED", True):
        return None
    return current_app.extensions.setdefault("ratelimit", Limiter())


def client_ip() -> str:
    for header in ("CF-Connecting-IP", "True-Client-IP"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"
