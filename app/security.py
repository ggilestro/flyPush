"""Security utilities: rate limiting, input sanitization."""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    """In-memory sliding-window rate limiter.

    Tracks request counts per key (IP address) within a time window
    and raises HTTP 429 when the limit is exceeded.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, key: str, now: float) -> None:
        """Remove expired timestamps for a key."""
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def reset(self) -> None:
        """Clear all tracked requests. Used in tests to avoid cross-test pollution."""
        with self._lock:
            self._requests.clear()

    def check(self, request: Request) -> None:
        """Check rate limit for the request. Raises HTTP 429 if exceeded."""
        key = self._get_client_ip(request)
        now = time.monotonic()

        with self._lock:
            self._cleanup(key, now)
            if len(self._requests[key]) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                )
            self._requests[key].append(now)


# Pre-configured limiters for different endpoint sensitivity levels
auth_limiter = RateLimiter(max_requests=10, window_seconds=60)
strict_limiter = RateLimiter(max_requests=5, window_seconds=60)


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcard characters in user input.

    Prevents user-supplied % and _ from being interpreted as wildcards
    in LIKE/ILIKE queries. Uses backslash as the escape character.

    Args:
        value: Raw user input string.

    Returns:
        Escaped string safe for use in LIKE/ILIKE patterns.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
