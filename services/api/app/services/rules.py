import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.crowding import CrowdThresholds, LevelState, OpenAlert, decide, step
from app.services.occupancy import zone_view
from app.services.views import latest_readings

OFFLINE_AFTER = timedelta(minutes=2)
ACTIVE = ("open", "acknowledged", "suspended")


@dataclass
class EvaluationResult:
    opened: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)


def thresholds_for(row: models.CrowdingThreshold | None) -> CrowdThresholds:
    if row is None:
        return CrowdThresholds()
    return CrowdThresholds(
        busy=float(row.busy_pct),
        crowded=float(row.crowded_pct),
        near_capacity=float(row.near_capacity_pct),
        hysteresis=float(row.hysteresis_pct),
        dwell=timedelta(seconds=row.dwell_seconds),
        alert_from=row.alert_from,  # type: ignore[arg-type]
    )


def _active_alerts(session: Session) -> dict[tuple[str, str], models.StaffAlert]:
    alerts = session.scalars(select(models.StaffAlert).where(models.StaffAlert.status.in_(ACTIVE)))
    return {(a.type, str(a.zone_id) if a.zone_id else str(a.device_id)): a for a in alerts}


def _last_resolved(session: Session) -> dict[str, datetime]:
    rows = session.execute(
        select(models.StaffAlert.zone_id, models.StaffAlert.resolved_at).where(
            models.StaffAlert.type == "crowding", models.StaffAlert.status == "resolved"
        )
    )
    latest: dict[str, datetime] = {}
    for zone_id, resolved_at in rows:
        if zone_id and resolved_at:
            key = str(zone_id)
            latest[key] = max(resolved_at, latest.get(key, resolved_at))
    return latest


def _resolve(alert: models.StaffAlert, now: datetime, result: EvaluationResult) -> None:
    alert.status, alert.resolved_at, alert.updated_at = "resolved", now, now
    result.resolved.append(f"{alert.type}:{alert.zone_id or alert.device_id}")


def _open(
    session: Session,
    alert_type: str,
    now: datetime,
    result: EvaluationResult,
    zone_id: uuid.UUID | None = None,
    device_id: str | None = None,
    level: str | None = None,
) -> None:
    session.add(
        models.StaffAlert(
            type=alert_type,
            zone_id=zone_id,
            device_id=device_id,
            level=level,
            status="open",
            opened_at=now,
            updated_at=now,
        )
    )
    result.opened.append(f"{alert_type}:{zone_id or device_id}")


def _crowding(
    session: Session,
    zone: models.SeatingZone,
    live: bool,
    percent: float | None,
    now: datetime,
    thresholds: CrowdThresholds,
    states: dict[str, models.ZoneCrowdState],
    alerts: dict[tuple[str, str], models.StaffAlert],
    resolved: dict[str, datetime],
    result: EvaluationResult,
) -> None:
    key = str(zone.id)
    row = states.get(key)
    if row is None:
        row = models.ZoneCrowdState(zone_id=zone.id, level="normal")
        session.add(row)
        states[key] = row
    state = LevelState(row.level, row.candidate, row.candidate_since)  # type: ignore[arg-type]
    if live and percent is not None:
        step(state, percent, now, thresholds)
    row.level, row.candidate, row.candidate_since, row.updated_at = (
        state.level,
        state.candidate,
        state.candidate_since,
        now,
    )
    existing = alerts.get(("crowding", key))
    snapshot = OpenAlert(existing.level, existing.status) if existing else None  # type: ignore[arg-type]
    action = decide(snapshot, state.level, live, now, resolved.get(key), thresholds)
    if action.kind == "open":
        _open(session, "crowding", now, result, zone_id=zone.id, level=action.level)
    elif existing is None or action.kind == "none":
        return
    elif action.kind == "resolve":
        _resolve(existing, now, result)
    elif action.kind == "suspend":
        existing.status, existing.updated_at = "suspended", now
        result.changed.append(f"crowding:{key}:suspended")
    else:
        existing.level, existing.updated_at = action.level, now
        if action.kind in ("reopen", "resume"):
            existing.status = "open"
            existing.acknowledged_at = existing.acknowledged_by = None
        result.changed.append(f"crowding:{key}:{action.kind}")


def evaluate(session: Session, now: datetime) -> EvaluationResult:
    result = EvaluationResult()
    zones = list(
        session.scalars(select(models.SeatingZone).where(models.SeatingZone.is_active, models.SeatingZone.is_monitored))
    )
    readings = latest_readings(session, [z.id for z in zones])
    thresholds = {str(t.zone_id): t for t in session.scalars(select(models.CrowdingThreshold))}
    states = {str(s.zone_id): s for s in session.scalars(select(models.ZoneCrowdState))}
    alerts = _active_alerts(session)
    resolved = _last_resolved(session)
    devices = {d.id: d for d in session.scalars(select(models.Device))}
    device_of_zone = zone_devices(session)

    for zone in zones:
        view = zone_view(str(zone.id), zone.name, zone.capacity, readings.get(zone.id), now)
        live = view.freshness == "live"
        _crowding(
            session,
            zone,
            live,
            view.percent,
            now,
            thresholds_for(thresholds.get(str(zone.id))),
            states,
            alerts,
            resolved,
            result,
        )
        device = devices.get(device_of_zone.get(str(zone.id), ""))
        device_online = device is not None and _online(device, now)
        stale_alert = alerts.get(("data_stale", str(zone.id)))
        is_stale = not live and device_online and device is not None and device.is_enabled
        if is_stale and stale_alert is None:
            _open(session, "data_stale", now, result, zone_id=zone.id)
        elif not is_stale and stale_alert is not None:
            _resolve(stale_alert, now, result)

    for device in devices.values():
        offline = device.kind == "camera" and device.is_enabled and not _online(device, now)
        offline_alert = alerts.get(("sensor_offline", device.id))
        if offline and offline_alert is None:
            _open(session, "sensor_offline", now, result, device_id=device.id)
        elif not offline and offline_alert is not None:
            _resolve(offline_alert, now, result)

    session.commit()
    return result


def _online(device: models.Device, now: datetime) -> bool:
    return device.last_heartbeat_at is not None and now - device.last_heartbeat_at <= OFFLINE_AFTER


def zone_devices(session: Session) -> dict[str, str]:
    mapping: dict[str, str] = {}
    layouts = session.scalars(select(models.ZoneLayout).where(models.ZoneLayout.is_current))
    for layout in layouts:
        for polygon in layout.polygons:
            if polygon.get("type") == "seating" and polygon.get("zone_id"):
                mapping[str(polygon["zone_id"])] = layout.device_id
    return mapping
