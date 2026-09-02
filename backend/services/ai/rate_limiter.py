"""
Simple in-memory rate limiting for AI requests: per-user per-minute, plus
a shared global daily cap (since one Gemini API key/free-tier quota is
shared across every visitor to the deployed app, not per-user).

This is intentionally in-memory, not Redis-backed - Tempora runs as a
single Render instance, and Redis would be real infrastructure overhead
for a portfolio project with no actual need for it (see project ground
rules on avoiding overengineering). The known trade-off: these counters
reset on every server restart/redeploy, and wouldn't be correct if the
app ever ran as multiple instances. Acceptable for this project's scale.
"""

import time
from collections import defaultdict, deque

import config


class RateLimitExceeded(Exception):
    pass


_user_request_times: dict[int, deque] = defaultdict(deque)
_global_daily_state = {"date": None, "count": 0}


def _check_global_daily_limit():
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _global_daily_state["date"] != today:
        _global_daily_state["date"] = today
        _global_daily_state["count"] = 0

    if _global_daily_state["count"] >= config.AI_GLOBAL_DAILY_LIMIT:
        raise RateLimitExceeded(
            "Tempora's AI assistant has reached its daily usage limit. Please try again tomorrow."
        )

    _global_daily_state["count"] += 1


def check_rate_limit(user_id: int):
    _check_global_daily_limit()

    now = time.monotonic()
    window_start = now - 60
    times = _user_request_times[user_id]

    while times and times[0] < window_start:
        times.popleft()

    if len(times) >= config.AI_USER_PER_MINUTE_LIMIT:
        raise RateLimitExceeded("You're sending requests too quickly. Please wait a moment and try again.")

    times.append(now)