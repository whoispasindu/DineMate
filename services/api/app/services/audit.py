import ipaddress
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app import models


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    try:
        return str(ipaddress.ip_address(request.client.host))
    except ValueError:
        return None


def record(
    session: Session,
    now: datetime,
    action: str,
    entity: str,
    entity_id: str,
    *,
    user: models.User | None = None,
    device_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    session.add(
        models.AuditLog(
            actor_user_id=user.id if user else None,
            actor_device_id=device_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=_jsonable(before),
            after=_jsonable(after),
            ip=client_ip(request),
            at=now,
        )
    )
