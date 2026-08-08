"""The dashboard login throttle — a public domain in front of this
(docs/ARCHITECTURE.md) can't be brute-forced against DEVPS_TOKEN."""

import time

from devps_agent import login_throttle


def setup_function() -> None:
    login_throttle._failed_logins.clear()


def test_not_rate_limited_below_threshold() -> None:
    ip = "1.2.3.4"
    for _ in range(login_throttle.ATTEMPT_LIMIT - 1):
        login_throttle.record_failure(ip)
    assert login_throttle.is_rate_limited(ip) is False


def test_rate_limited_at_threshold() -> None:
    ip = "1.2.3.4"
    for _ in range(login_throttle.ATTEMPT_LIMIT):
        login_throttle.record_failure(ip)
    assert login_throttle.is_rate_limited(ip) is True


def test_old_attempts_outside_window_dont_count() -> None:
    ip = "1.2.3.4"
    stale = time.time() - login_throttle.WINDOW_SECONDS - 1
    login_throttle._failed_logins[ip] = [stale] * login_throttle.ATTEMPT_LIMIT
    assert login_throttle.is_rate_limited(ip) is False


def test_different_ips_tracked_independently() -> None:
    for _ in range(login_throttle.ATTEMPT_LIMIT):
        login_throttle.record_failure("1.2.3.4")
    assert login_throttle.is_rate_limited("1.2.3.4") is True
    assert login_throttle.is_rate_limited("5.6.7.8") is False


def test_record_success_clears_failures() -> None:
    ip = "1.2.3.4"
    for _ in range(login_throttle.ATTEMPT_LIMIT):
        login_throttle.record_failure(ip)
    login_throttle.record_success(ip)
    assert login_throttle.is_rate_limited(ip) is False
