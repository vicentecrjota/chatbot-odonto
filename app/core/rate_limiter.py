"""Proteção contra abuso por rate limiting por telefone."""

from collections import defaultdict
from datetime import datetime, timedelta


class RateLimiter:
    def __init__(self, max_requests: int = 30, window_minutes: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(minutes=window_minutes)
        self.requests: dict[str, list[datetime]] = defaultdict(list)

    def is_allowed(self, phone: str) -> bool:
        """Retorna True se o telefone pode enviar mensagem."""
        now = datetime.utcnow()
        cutoff = now - self.window

        self.requests[phone] = [
            ts for ts in self.requests[phone] if ts > cutoff
        ]

        if len(self.requests[phone]) >= self.max_requests:
            return False

        self.requests[phone].append(now)
        return True


rate_limiter = RateLimiter()
