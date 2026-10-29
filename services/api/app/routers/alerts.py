import uuid
from typing import Any, Literal

from fastapi import APIRouter

from app import models
from app.core.config import get_settings
from app.core.deps import NowDep, SessionDep
from app.core.errors import ApiError, not_found
from app.core.staff_auth import StaffDep
from app.schemas import ErrorResponse
from app.schemas_staff import AlertFeed, ConsoleOverview, StaffAlertList, StaffAlertResult
from app.services.staff_views import alert_schema, console_overview, device_zones, notices, staff_alerts, zone_names

router = APIRouter(tags=["alerts"])

STAFF_RESPONSES: dict[int | str, dict[str, Any]] = {401: {"model": ErrorResponse}}
ACTIVE = ("open", "acknowledged", "suspended")


@router.get("/notices", response_model=AlertFeed)
def get_notices(session: SessionDep, now: NowDep) -> AlertFeed:
    return notices(session, now)


@router.get("/alerts", response_model=StaffAlertList, responses=STAFF_RESPONSES)
def list_alerts(
    _staff: StaffDep,
    session: SessionDep,
    now: NowDep,
    status: Literal["active", "open", "acknowledged", "suspended", "resolved", "all"] = "active",
) -> StaffAlertList:
    statuses = ACTIVE if status == "active" else None if status == "all" else (status,)
    return StaffAlertList(server_time=now, items=staff_alerts(session, statuses))


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=StaffAlertResult,
    responses={**STAFF_RESPONSES, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def acknowledge_alert(alert_id: str, staff: StaffDep, session: SessionDep, now: NowDep) -> StaffAlertResult:
    try:
        key = uuid.UUID(alert_id)
    except ValueError as exc:
        raise not_found("Alert", alert_id) from exc
    alert = session.get(models.StaffAlert, key)
    if alert is None:
        raise not_found("Alert", alert_id)
    if alert.status not in ("open", "acknowledged"):
        raise ApiError(409, "conflict", f"A {alert.status} alert can't be acknowledged.", {"status": alert.status})
    if alert.status == "open":
        alert.status, alert.acknowledged_at, alert.acknowledged_by, alert.updated_at = "acknowledged", now, staff, now
        session.commit()
    body = alert_schema(alert, zone_names(session), device_zones(session))
    return StaffAlertResult(server_time=now, **body.model_dump())


@router.get("/console/overview", response_model=ConsoleOverview, responses=STAFF_RESPONSES)
def get_console_overview(
    _staff: StaffDep, session: SessionDep, now: NowDep, canteen_id: str | None = None
) -> ConsoleOverview:
    return console_overview(session, now, get_settings().simulation_mode, canteen_id)
