import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

ALGORITHM = "HS256"
REFRESH_COOKIE = "dinemate_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: str, role: str, settings: Settings, now: datetime | None = None) -> tuple[str, int]:
    issued = now or datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    claims = {"sub": user_id, "role": role, "typ": "access", "iat": issued, "exp": issued + lifetime}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM), int(lifetime.total_seconds())


def decode_access_token(token: str, settings: Settings) -> dict[str, Any] | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp"]})
    except jwt.PyJWTError:
        return None
    return claims if claims.get("typ") == "access" else None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_s:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter()
