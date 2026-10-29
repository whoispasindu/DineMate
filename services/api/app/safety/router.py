import uuid
from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app import models
from app.core.auth import ADMIN, SAFETY_OFFICER, require_roles
from app.core.config import get_settings
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import RealNowDep
from app.core.errors import ApiError, not_found
from app.safety import service
from app.safety.models import SafetyEvent, SafetyEventAck, SafetySource
from app.safety.schemas import (
    AcknowledgeIn,
    ResolveIn,
    SafetyAck,
    SafetyActive,
    SafetyEventAccepted,
    SafetyEventIn,
    SafetySourceHealth,
    SafetySourceList,
    SimulateIn,
    SourceHeartbeatAccepted,
    SourceHeartbeatIn,
    StaffSafetyEvent,
    StaffSafetyEventList,
    StaffSafetyEventResult,
)
from app.safety.signing import SignedSource
from app.schemas import ErrorResponse
from app.services.audit import record

router = APIRouter(prefix="/safety", tags=["safety"])

SafetyStaff = Annotated[models.User, Depends(require_roles(ADMIN, SAFETY_OFFICER))]
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}
RECENT_RESOLVED = timedelta(days=7)


def staff_event(
    session: SessionDep, event: SafetyEvent, canteens: dict[str, str], zones: dict[uuid.UUID, str]
) -> StaffSafetyEvent:
    resolver = session.get(models.User, event.resolved_by) if event.resolved_by else None
    return StaffSafetyEvent(
        id=str(event.id),
        event_type=event.event_type,  # type: ignore[arg-type]
        title=service.title_for(event),
        severity=event.severity,  # type: ignore[arg-type]
        status=event.status,  # type: ignore[arg-type]
        is_simulation=event.is_simulation,
        label=service.SIMULATION_LABEL if event.is_simulation else None,
        canteen_id=event.canteen_id,
        canteen_name=canteens.get(event.canteen_id) if event.canteen_id else None,
        zone_name=zones.get(event.zone_id) if event.zone_id else None,
        source_id=event.source_id,
        source_name=event.source.name,
        source_kind=event.source.kind,  # type: ignore[arg-type]
        occurred_at=event.occurred_at,
        received_at=event.received_at,
        last_seen_at=event.last_seen_at,
        repeat_count=event.repeat_count,
        note=event.note,
        instructions=service.instructions_for(session, event),
        acks=[SafetyAck(user_name=a.user_name, acknowledged_at=a.acknowledged_at, note=a.note) for a in event.acks],
        resolved_by_name=resolver.display_name if resolver else ("System" if event.resolved_at else None),
        resolved_at=event.resolved_at,
        resolution_note=event.resolution_note,
    )


def staff_result(session: SessionDep, event: SafetyEvent, now: Any) -> StaffSafetyEventResult:
    return StaffSafetyEventResult(
        server_time=now,
        event=staff_event(session, event, service.canteen_names(session), service.zone_names(session, [event])),
    )


def _audit_after(event: SafetyEvent) -> dict[str, Any]:
    return {
        "status": event.status,
        "event_type": event.event_type,
        "is_simulation": event.is_simulation,
        "label": service.SIMULATION_LABEL if event.is_simulation else None,
        "repeat_count": event.repeat_count,
    }


def _location(session: SessionDep, canteen_id: str | None, zone_id: str | None) -> tuple[str | None, uuid.UUID | None]:
    if canteen_id is not None and session.get(models.Canteen, canteen_id) is None:
        raise ApiError(422, "validation_error", "Unknown canteen.", {"canteen_id": canteen_id})
    if zone_id is None:
        return canteen_id, None
    try:
        zone = session.get(models.SeatingZone, uuid.UUID(zone_id))
    except ValueError:
        zone = None
    if zone is None or (canteen_id is not None and zone.canteen_id != canteen_id):
        raise ApiError(422, "validation_error", "Unknown zone for this canteen.", {"zone_id": zone_id})
    return zone.canteen_id, zone.id


def _accepted(ingested: service.Ingested, now: Any) -> SafetyEventAccepted:
    event = ingested.event
    return SafetyEventAccepted(
        server_time=now,
        id=str(event.id),
        status=event.status,  # type: ignore[arg-type]
        is_simulation=event.is_simulation,
        severity=event.severity,  # type: ignore[arg-type]
        repeat_count=event.repeat_count,
        merged=ingested.merged,
        label=service.SIMULATION_LABEL if event.is_simulation else None,
    )


@router.post("/events", status_code=202, response_model=SafetyEventAccepted, responses=RESPONSES)
def post_event(
    payload: SafetyEventIn,
    source: SignedSource,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> SafetyEventAccepted:
    canteen_id, zone_id = _location(session, payload.location.canteen_id, payload.location.zone_id)
    occurred = now - max(timedelta(0), real_now - payload.occurred_at)
    ingested = service.ingest(
        session,
        source,
        payload.external_event_id,
        payload.event_type,
        canteen_id,
        zone_id,
        occurred,
        payload.is_simulation,
        now,
    )
    source.last_heartbeat_at = now
    if not ingested.merged:
        record(
            session,
            real_now,
            "safety.event_received",
            "safety_event",
            str(ingested.event.id),
            device_id=source.id,
            after={**_audit_after(ingested.event), "claimed_simulation": payload.is_simulation},
            request=request,
        )
    session.commit()
    return _accepted(ingested, now)


@router.post("/heartbeat", response_model=SourceHeartbeatAccepted, responses=RESPONSES)
def post_heartbeat(
    payload: SourceHeartbeatIn, source: SignedSource, session: SessionDep, now: NowDep
) -> SourceHeartbeatAccepted:
    source.last_heartbeat_at = now
    service.check_sources(session, now)
    session.commit()
    return SourceHeartbeatAccepted(server_time=now, source_id=source.id)


@router.get("/active", response_model=SafetyActive)
def get_active(session: SessionDep, now: NowDep) -> SafetyActive:
    active, events = service.public_status(session)
    return SafetyActive(server_time=now, active=active, events=events)


@router.get("/events", response_model=StaffSafetyEventList, responses=RESPONSES)
def list_events(
    user: SafetyStaff, session: SessionDep, now: NowDep, status: Literal["open", "resolved", "all"] = "open"
) -> StaffSafetyEventList:
    stmt = select(SafetyEvent).order_by(SafetyEvent.received_at.desc())
    if status == "open":
        stmt = stmt.where(SafetyEvent.status.in_(service.OPEN))
    elif status == "resolved":
        stmt = stmt.where(SafetyEvent.status == "resolved", SafetyEvent.resolved_at >= now - RECENT_RESOLVED)
    events = sorted(session.scalars(stmt.limit(200)), key=lambda e: (e.status != "active", e.status != "acknowledged"))
    canteens, zones = service.canteen_names(session), service.zone_names(session, events)
    return StaffSafetyEventList(
        server_time=now,
        simulation_mode=get_settings().simulation_mode,
        items=[staff_event(session, e, canteens, zones) for e in events],
    )


def _event(session: SessionDep, event_id: str) -> SafetyEvent:
    try:
        event = session.get(SafetyEvent, uuid.UUID(event_id))
    except ValueError:
        event = None
    if event is None:
        raise not_found("Safety event", event_id)
    return event


@router.post("/events/{event_id}/acknowledge", response_model=StaffSafetyEventResult, responses=RESPONSES)
def acknowledge_event(
    event_id: str,
    payload: AcknowledgeIn,
    user: SafetyStaff,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> StaffSafetyEventResult:
    event = _event(session, event_id)
    if event.status == "resolved":
        raise ApiError(409, "conflict", "This event is already resolved.", {"status": event.status})
    before = _audit_after(event)
    event.status = "acknowledged"
    session.add(
        SafetyEventAck(
            event_id=event.id,
            user_id=user.id,
            user_name=user.display_name,
            acknowledged_at=now,
            note=payload.note or None,
        )
    )
    session.flush()
    session.refresh(event)
    record(
        session,
        real_now,
        "safety.acknowledge",
        "safety_event",
        event_id,
        user=user,
        before=before,
        after={**_audit_after(event), "note": payload.note},
        request=request,
    )
    session.commit()
    return staff_result(session, event, now)


@router.post("/events/{event_id}/resolve", response_model=StaffSafetyEventResult, responses=RESPONSES)
def resolve_event(
    event_id: str,
    payload: ResolveIn,
    user: SafetyStaff,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> StaffSafetyEventResult:
    event = _event(session, event_id)
    if event.status == "resolved":
        raise ApiError(409, "conflict", "This event is already resolved.", {"status": event.status})
    before = _audit_after(event)
    event.status, event.resolved_by, event.resolved_at, event.resolution_note = "resolved", user.id, now, payload.note
    record(
        session,
        real_now,
        "safety.resolve",
        "safety_event",
        event_id,
        user=user,
        before=before,
        after={**_audit_after(event), "note": payload.note},
        request=request,
    )
    session.commit()
    return staff_result(session, event, now)


@router.post("/simulate", status_code=201, response_model=StaffSafetyEventResult, responses=RESPONSES)
def simulate(
    payload: SimulateIn,
    user: SafetyStaff,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> StaffSafetyEventResult:
    if not get_settings().simulation_mode:
        raise ApiError(403, "simulation_disabled", "Simulated safety events are only allowed in simulation mode.")
    canteen_id, zone_id = _location(session, payload.canteen_id, payload.zone_id)
    source = service.ensure_simulator_source(session)
    ingested = service.ingest(
        session,
        source,
        f"console-{uuid.uuid4()}",
        payload.event_type,
        canteen_id,
        zone_id,
        now,
        True,
        now,
        note=payload.note or None,
    )
    record(
        session,
        real_now,
        "safety.simulate",
        "safety_event",
        str(ingested.event.id),
        user=user,
        after={**_audit_after(ingested.event), "merged": ingested.merged, "note": payload.note},
        request=request,
    )
    session.commit()
    return staff_result(session, ingested.event, now)


@router.get("/sources", response_model=SafetySourceList, responses=RESPONSES)
def list_sources(user: SafetyStaff, session: SessionDep, now: NowDep) -> SafetySourceList:
    items = []
    for s in session.scalars(select(SafetySource).order_by(SafetySource.kind, SafetySource.id)):
        state = (
            "never_connected"
            if s.last_heartbeat_at is None
            else "online"
            if service.source_online(s, now)
            else "offline"
        )
        items.append(
            SafetySourceHealth(
                id=s.id,
                name=s.name,
                kind=s.kind,  # type: ignore[arg-type]
                is_enabled=s.is_enabled,
                last_heartbeat_at=s.last_heartbeat_at,
                state=state,  # type: ignore[arg-type]
            )
        )
    return SafetySourceList(server_time=now, items=items)
