import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select

from app.core.deps import SessionDep
from app.core.device_auth import RealNowDep, hash_token
from app.core.errors import ApiError
from app.core.security import RateLimiter
from app.safety.models import SafetySource
from app.services.audit import client_ip, record

SCHEME = "Device"
SIGNATURE_PREFIX = "sha256="
MAX_SKEW = timedelta(seconds=60)
INGEST_PER_SECOND = 10

log = logging.getLogger("dinemate.safety")
ingest_limiter = RateLimiter()


def signature(token: str, timestamp: str, body: bytes) -> str:
    digest = hmac.new(token.encode("utf-8"), timestamp.encode("utf-8") + b"." + body, hashlib.sha256).hexdigest()
    return SIGNATURE_PREFIX + digest


def _reject(message: str) -> ApiError:
    return ApiError(401, "invalid_signature", message)


async def signed_source(
    request: Request,
    session: SessionDep,
    real_now: RealNowDep,
    authorization: Annotated[str | None, Header()] = None,
    x_signature: Annotated[str | None, Header()] = None,
    x_timestamp: Annotated[str | None, Header()] = None,
) -> SafetySource:
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()
    source = (
        session.scalars(select(SafetySource).where(SafetySource.token_hash == hash_token(token))).first()
        if scheme == SCHEME and token
        else None
    )
    if source is None:
        log.warning("safety ingest rejected: unknown source from %s", client_ip(request))
        raise ApiError(401, "unauthenticated", "A valid safety source token is required.")
    if not source.is_enabled:
        raise ApiError(403, "forbidden", "This safety source is disabled.", {"source_id": source.id})
    body = await request.body()
    reason = _check(token, x_signature, x_timestamp, body, real_now)
    if reason is not None:
        log.warning("safety ingest rejected for %s: %s", source.id, reason)
        record(
            session,
            real_now,
            "safety.ingest_rejected",
            "safety_source",
            source.id,
            device_id=source.id,
            after={"reason": reason, "path": request.url.path},
            request=request,
        )
        session.commit()
        raise _reject(reason)
    if not ingest_limiter.allow(source.id, INGEST_PER_SECOND, 1.0):
        raise ApiError(429, "rate_limited", "Too many safety messages from this source.", {"source_id": source.id})
    return source


def _check(token: str, sent: str | None, timestamp: str | None, body: bytes, real_now: datetime) -> str | None:
    if not sent or not timestamp:
        return "Missing X-Signature or X-Timestamp."
    try:
        stamped = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "X-Timestamp is not an ISO 8601 time."
    if stamped.tzinfo is None:
        return "X-Timestamp needs a time zone."
    if abs(real_now - stamped) > MAX_SKEW:
        return "X-Timestamp is outside the 60 s window."
    if not hmac.compare_digest(signature(token, timestamp, body), sent):
        return "Signature does not match."
    return None


SignedSource = Annotated[SafetySource, Depends(signed_source)]
