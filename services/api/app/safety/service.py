import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.config import get_settings
from app.core.device_auth import hash_token
from app.safety.models import SafetyEvent, SafetyInstruction, SafetySource

SIMULATOR_SOURCE_ID = "safety-sim"
SIMULATION_LABEL = "SIMULATION — NOT A REAL EMERGENCY"
FALLBACK_INSTRUCTIONS = "Follow instructions from campus staff and official alarms."
MERGE_WINDOW = timedelta(minutes=5)
OFFLINE_AFTER = timedelta(seconds=60)
OPEN = ("active", "acknowledged")
SEVERITY = {"fire_alarm": "critical", "evacuation": "critical", "test_notice": "info", "integration_offline": "warning"}
TITLES = {
    "fire_alarm": "Fire alarm",
    "evacuation": "Evacuation notice",
    "test_notice": "Test notice",
    "integration_offline": "Alarm integration offline",
}


@dataclass
class Ingested:
    event: SafetyEvent
    merged: bool


def ensure_simulator_source(session: Session) -> SafetySource:
    source = session.get(SafetySource, SIMULATOR_SOURCE_ID)
    if source is None:
        source = SafetySource(
            id=SIMULATOR_SOURCE_ID,
            name="Safety simulator",
            kind="simulator",
            token_hash=hash_token(get_settings().safety_simulator_token),
        )
        session.add(source)
        session.flush()
    return source


def title_for(event: SafetyEvent) -> str:
    title = TITLES.get(event.event_type, event.event_type)
    return f"{title} (simulated)" if event.is_simulation else title


def instructions_for(session: Session, event: SafetyEvent) -> str:
    rows = session.scalars(
        select(SafetyInstruction).where(
            SafetyInstruction.is_active,
            SafetyInstruction.event_type == event.event_type,
            (SafetyInstruction.canteen_id == event.canteen_id) | SafetyInstruction.canteen_id.is_(None),
        )
    ).all()
    specific = next((r for r in rows if r.canteen_id is not None), None)
    chosen = specific or next(iter(rows), None)
    return chosen.body if chosen else FALLBACK_INSTRUCTIONS


def _open_match(
    session: Session,
    event_type: str,
    canteen_id: str | None,
    zone_id: uuid.UUID | None,
    simulation: bool,
    now: datetime,
) -> SafetyEvent | None:
    stmt = select(SafetyEvent).where(
        SafetyEvent.event_type == event_type,
        SafetyEvent.is_simulation == simulation,
        SafetyEvent.status.in_(OPEN),
        SafetyEvent.last_seen_at >= now - MERGE_WINDOW,
        SafetyEvent.canteen_id.is_(None) if canteen_id is None else SafetyEvent.canteen_id == canteen_id,
        SafetyEvent.zone_id.is_(None) if zone_id is None else SafetyEvent.zone_id == zone_id,
    )
    return session.scalars(stmt.order_by(SafetyEvent.received_at.desc())).first()


def _repeat(session: Session, event: SafetyEvent, now: datetime) -> Ingested:
    event.repeat_count = SafetyEvent.repeat_count + 1
    event.last_seen_at = now
    session.flush()
    session.refresh(event)
    return Ingested(event, merged=True)


def ingest(
    session: Session,
    source: SafetySource,
    external_event_id: str,
    event_type: str,
    canteen_id: str | None,
    zone_id: uuid.UUID | None,
    occurred_at: datetime,
    claims_simulation: bool,
    now: datetime,
    note: str | None = None,
    merge: bool = True,
) -> Ingested:
    simulation = claims_simulation or source.kind == "simulator"
    same_id = select(SafetyEvent).where(
        SafetyEvent.source_id == source.id, SafetyEvent.external_event_id == external_event_id
    )
    existing = session.scalars(same_id).first()
    if existing is not None:
        return _repeat(session, existing, now)
    match = _open_match(session, event_type, canteen_id, zone_id, simulation, now) if merge else None
    if match is not None:
        return _repeat(session, match, now)
    event = SafetyEvent(
        source_id=source.id,
        external_event_id=external_event_id,
        event_type=event_type,
        severity=SEVERITY[event_type],
        canteen_id=canteen_id,
        zone_id=zone_id,
        occurred_at=min(occurred_at, now),
        received_at=now,
        last_seen_at=now,
        is_simulation=simulation,
        status="active",
        repeat_count=1,
        note=note,
    )
    try:
        with session.begin_nested():
            session.add(event)
    except IntegrityError:
        raced = session.scalars(same_id).first()
        if raced is None:
            raise
        return _repeat(session, raced, now)
    return Ingested(event, merged=False)


def open_events(session: Session, public: bool) -> list[SafetyEvent]:
    stmt = select(SafetyEvent).where(SafetyEvent.status.in_(OPEN))
    if public:
        stmt = stmt.where(SafetyEvent.severity != "warning")
    events = list(session.scalars(stmt.order_by(SafetyEvent.received_at.desc())))
    return sorted(events, key=lambda e: e.status != "active")


def source_online(source: SafetySource, now: datetime) -> bool:
    return source.last_heartbeat_at is not None and now - source.last_heartbeat_at <= OFFLINE_AFTER


def check_sources(session: Session, now: datetime) -> list[SafetyEvent]:
    changed: list[SafetyEvent] = []
    for source in session.scalars(select(SafetySource).where(SafetySource.is_enabled)):
        if source.last_heartbeat_at is None:
            continue
        warning = session.scalars(
            select(SafetyEvent).where(
                SafetyEvent.source_id == source.id,
                SafetyEvent.event_type == "integration_offline",
                SafetyEvent.status.in_(OPEN),
            )
        ).first()
        if not source_online(source, now) and warning is None:
            changed.append(
                ingest(
                    session,
                    source,
                    f"offline-{source.id}-{int(source.last_heartbeat_at.timestamp())}",
                    "integration_offline",
                    None,
                    None,
                    source.last_heartbeat_at + OFFLINE_AFTER,
                    False,
                    now,
                    note=f"No heartbeat from {source.name} since {source.last_heartbeat_at.isoformat()}.",
                    merge=False,
                ).event
            )
        elif source_online(source, now) and warning is not None:
            warning.status = "resolved"
            warning.resolved_at = now
            warning.resolution_note = "Heartbeat resumed."
            changed.append(warning)
    return changed


def zone_names(session: Session, events: list[SafetyEvent]) -> dict[uuid.UUID, str]:
    ids = [e.zone_id for e in events if e.zone_id is not None]
    if not ids:
        return {}
    return {z.id: z.name for z in session.scalars(select(models.SeatingZone).where(models.SeatingZone.id.in_(ids)))}


def canteen_names(session: Session) -> dict[str, str]:
    return {cid: name for cid, name in session.execute(select(models.Canteen.id, models.Canteen.name))}


def public_event(session: Session, event: SafetyEvent, canteens: dict[str, str]) -> schemas.SafetyEvent:
    return schemas.SafetyEvent(
        id=str(event.id),
        event_type=event.event_type,
        title=title_for(event),
        canteen_name=canteens.get(event.canteen_id) if event.canteen_id else None,
        occurred_at=event.occurred_at,
        is_simulation=event.is_simulation,
        status=event.status,  # type: ignore[arg-type]
        source_name=event.source.name,
        instructions=instructions_for(session, event),
    )


def public_status(session: Session) -> tuple[bool, list[schemas.SafetyEvent]]:
    canteens = canteen_names(session)
    events = [public_event(session, e, canteens) for e in open_events(session, public=True)]
    return bool(events), events
