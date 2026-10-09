"""Small in-memory rate limiter (one server process; it forgets everything when the server restarts)."""
import threading, time
from collections import defaultdict, deque
from fastapi import HTTPException, Request

_hits = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()      # the LAST entry is the one the platform's proxy added, not one the client typed
    return request.client.host if request.client else "unknown"


def _fresh(q: deque, now: float, window: int) -> deque:
    while q and q[0] <= now - window:
        q.popleft()
    return q


def hit(key: str, limit: int, window_s: int, message: str) -> None:
    """Count one use of `key`; refuse with 429 once it was used `limit` times within `window_s` seconds."""
    now = time.time()
    with _lock:
        q = _fresh(_hits[key], now, window_s)
        if len(q) >= limit:
            raise HTTPException(429, message)
        q.append(now)
        if len(_hits) > 20000:                  # keep memory bounded
            for k in [k for k, v in _hits.items() if not v or v[-1] < now - 86400]:
                del _hits[k]


def failures(key: str, window_s: int) -> int:
    with _lock:
        return len(_fresh(_hits[key], time.time(), window_s))


def record(key: str) -> None:
    with _lock:
        _hits[key].append(time.time())


def clear(key: str) -> None:
    with _lock:
        _hits.pop(key, None)
