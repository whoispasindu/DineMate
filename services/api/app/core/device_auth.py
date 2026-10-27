import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header

from app import models
from app.core.deps import SessionDep
from app.core.errors import ApiError

SCHEME = "Device"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, token_hash: str | None) -> bool:
    return token_hash is not None and hmac.compare_digest(hash_token(token), token_hash)


def _unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated", "A valid device token is required.")


def authenticated_device(
    device_id: str,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> models.Device:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme != SCHEME or not token:
        raise _unauthenticated()
    device = session.get(models.Device, device_id)
    if device is None or not token_matches(token.strip(), device.token_hash):
        raise _unauthenticated()
    if not device.is_enabled:
        raise ApiError(403, "forbidden", "This device is disabled.", {"device_id": device_id})
    return device


def get_real_now() -> datetime:
    return datetime.now(UTC)


DeviceDep = Annotated[models.Device, Depends(authenticated_device)]
RealNowDep = Annotated[datetime, Depends(get_real_now)]
