"""In-process login throttle for the dashboard — pure logic, no FastAPI
import, so it's testable the same way registry.py/ports.py are (no need
for fastapi installed just to run this module's tests).

Fine for a single-uvicorn-worker deploy, same assumption the SQLite
registry already makes. Keyed by client IP so a public domain in front of
the dashboard (see docs/ARCHITECTURE.md) can't be brute-forced against
DEVPS_TOKEN.
"""

import time
from collections import defaultdict

ATTEMPT_LIMIT = 5
WINDOW_SECONDS = 300

_failed_logins: dict[str, list[float]] = defaultdict(list)


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    attempts = _failed_logins[ip]
    attempts[:] = [t for t in attempts if now - t < WINDOW_SECONDS]
    return len(attempts) >= ATTEMPT_LIMIT


def record_failure(ip: str) -> None:
    _failed_logins[ip].append(time.time())


def record_success(ip: str) -> None:
    _failed_logins.pop(ip, None)
