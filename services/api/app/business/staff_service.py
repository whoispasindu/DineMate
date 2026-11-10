import hashlib
import hmac
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models
from app.business import staff_schemas as ss
from app.business.coverage import Interval, QueuePoint, coverage, queue_alerts
from app.business.models import FaceTemplate, QueueReading, StaffMember, StaffPresence, TillItem, TillOrder
from app.business.service import day_bounds, tz_of
from app.business.templates import TemplatesUnavailable, vault_for
from app.business.till import parse_csv
from app.core.config import Settings
from app.core.errors import ApiError

AREAS = ("counter", "kitchen", "floor")
LIVE_LINK_TTL = timedelta(seconds=60)
SHEET_DAYS = 7


def conflict(message: str, **details: Any) -> ApiError:
    return ApiError(409, "conflict", message, details)


def invalid(message: str, **details: Any) -> ApiError:
    return ApiError(422, "validation_error", message, details)


def template_ids(session: Session, staff_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not staff_ids:
        return set()
    return set(session.scalars(select(FaceTemplate.staff_id).where(FaceTemplate.staff_id.in_(staff_ids))))


def staff_out(member: StaffMember, has_template: bool) -> ss.StaffOut:
    return ss.StaffOut(
        id=str(member.id),
        display_name=member.display_name,
        role_label=member.role_label,
        method=member.method,  # type: ignore[arg-type]
        badge_code=member.badge_code,
        till_code=member.till_code,
        consent_at=member.consent_at,
        consent_version=member.consent_version,
        has_template=has_template,
        active=member.active,
        is_sample=member.is_sample,
    )


def venue_staff(session: Session, venue_id: str) -> list[StaffMember]:
    return list(
        session.scalars(select(StaffMember).where(StaffMember.venue_id == venue_id).order_by(StaffMember.display_name))
    )


def list_staff(session: Session, venue: models.Canteen, now: datetime) -> ss.StaffList:
    members = venue_staff(session, venue.id)
    faces = template_ids(session, [m.id for m in members])
    return ss.StaffList(server_time=now, venue_id=venue.id, items=[staff_out(m, m.id in faces) for m in members])


def load_staff(session: Session, staff_id: str) -> StaffMember | None:
    try:
        return session.get(StaffMember, uuid.UUID(staff_id))
    except ValueError:
        return None


def _check_unique(session: Session, venue_id: str, member_id: uuid.UUID | None, **fields: Any) -> None:
    for column, value in fields.items():
        if value is None:
            continue
        clash = session.scalar(
            select(StaffMember.id).where(
                StaffMember.venue_id == venue_id,
                getattr(StaffMember, column) == value,
                StaffMember.id != member_id if member_id else True,
            )
        )
        if clash is not None:
            raise conflict(f"Another worker already has this {column.replace('_', ' ')}.", **{column: str(value)})


def create_staff(session: Session, venue: models.Canteen, payload: ss.StaffIn, now: datetime) -> StaffMember:
    name = payload.display_name.strip()
    _check_unique(
        session, venue.id, None, display_name=name, badge_code=payload.badge_code, till_code=payload.till_code
    )
    member = StaffMember(
        venue_id=venue.id,
        display_name=name,
        role_label=payload.role_label.strip(),
        method=payload.method,
        badge_code=payload.badge_code,
        till_code=payload.till_code,
        created_at=now,
    )
    session.add(member)
    session.flush()
    return member


def patch_staff(session: Session, member: StaffMember, payload: ss.StaffPatch) -> None:
    changes = payload.model_dump(exclude_unset=True)
    if "display_name" in changes and changes["display_name"] is not None:
        changes["display_name"] = changes["display_name"].strip()
    _check_unique(
        session,
        member.venue_id,
        member.id,
        **{k: v for k, v in changes.items() if k in ("display_name", "badge_code", "till_code")},
    )
    if changes.get("till_code") == "":
        changes["till_code"] = None
    for key, value in changes.items():
        if key in ("display_name", "method", "active") and value is None:
            continue
        setattr(member, key, value)
    if member.method != "face":
        session.execute(delete(FaceTemplate).where(FaceTemplate.staff_id == member.id))


def withdraw_consent(session: Session, member: StaffMember) -> None:
    member.consent_at = None
    member.consent_version = None
    session.execute(delete(FaceTemplate).where(FaceTemplate.staff_id == member.id))
    session.execute(delete(StaffPresence).where(StaffPresence.staff_id == member.id))


def store_template(
    session: Session, settings: Settings, member: StaffMember, vector: list[float], now: datetime
) -> None:
    if member.consent_at is None:
        raise conflict("Record this worker's written consent before enrolling a face.")
    if member.method != "face" or not member.active:
        raise conflict("Only active workers who chose face recognition can be enrolled.")
    try:
        vault = vault_for(settings)
        sealed = vault.seal(vector)
    except TemplatesUnavailable as exc:
        raise ApiError(403, "templates_disabled", str(exc)) from exc
    except ValueError as exc:
        raise invalid(str(exc)) from exc
    session.merge(FaceTemplate(staff_id=member.id, sealed=sealed, created_at=now))


def open_windows(venue: models.Canteen, day: date) -> list[Interval]:
    tz = tz_of(venue)
    return [
        Interval(datetime.combine(day, h.opens, tzinfo=tz), datetime.combine(day, h.closes, tzinfo=tz))
        for h in venue.hours
        if h.weekday == day.weekday()
    ]


def presence_between(
    session: Session, staff_ids: list[uuid.UUID], start: datetime, end: datetime, now: datetime
) -> dict[uuid.UUID, list[tuple[str, Interval]]]:
    result: dict[uuid.UUID, list[tuple[str, Interval]]] = defaultdict(list)
    if not staff_ids:
        return result
    rows = session.scalars(
        select(StaffPresence).where(
            StaffPresence.staff_id.in_(staff_ids),
            StaffPresence.started_at < end,
            func.coalesce(StaffPresence.ended_at, now) > start,
        )
    )
    for row in rows:
        clipped = Interval(max(row.started_at, start), min(row.ended_at or now, end))
        if clipped.end > clipped.start:
            result[row.staff_id].append((row.area, clipped))
    return result


def area_minutes(parts: list[tuple[str, Interval]]) -> ss.AreaMinutes:
    totals: Counter[str] = Counter()
    for area, interval in parts:
        totals[area] += interval.minutes
    return ss.AreaMinutes(**{a: round(totals[a]) for a in AREAS})


def orders_between(session: Session, venue_id: str, start: datetime, end: datetime) -> list[TillOrder]:
    return list(
        session.scalars(
            select(TillOrder)
            .where(TillOrder.venue_id == venue_id, TillOrder.at >= start, TillOrder.at < end)
            .order_by(TillOrder.at)
        )
    )


def items_of(session: Session, order_ids: list[int]) -> dict[int, list[TillItem]]:
    grouped: dict[int, list[TillItem]] = defaultdict(list)
    if order_ids:
        for item in session.scalars(select(TillItem).where(TillItem.order_id.in_(order_ids))):
            grouped[item.order_id].append(item)
    return grouped


def item_counts(counter: Counter[str]) -> list[ss.ItemCount]:
    return [ss.ItemCount(name=name, qty=qty) for name, qty in counter.most_common()]


def report(session: Session, venue: models.Canteen, day: date, now: datetime) -> ss.StaffReport:
    tz = tz_of(venue)
    start, end = day_bounds(day, tz)
    members = venue_staff(session, venue.id)
    presence = presence_between(session, [m.id for m in members], start, end, now)
    windows = [Interval(w.start, min(w.end, max(now, w.start))) for w in open_windows(venue, day)]
    counter_parts = [i for parts in presence.values() for area, i in parts if area == "counter"]
    cover = coverage(counter_parts, windows)
    points = [
        QueuePoint(r.at, r.people)
        for r in session.scalars(
            select(QueueReading).where(
                QueueReading.venue_id == venue.id,
                QueueReading.at >= start,
                QueueReading.at < end,
                QueueReading.people.is_not(None),
            )
        )
        if r.people is not None
    ]
    orders = orders_between(session, venue.id, start, end)
    items = items_of(session, [o.id for o in orders])
    served: dict[uuid.UUID, Counter[str]] = defaultdict(Counter)
    order_count: Counter[uuid.UUID] = Counter()
    for order in orders:
        if order.staff_id is None:
            continue
        order_count[order.staff_id] += 1
        for item in items[order.id]:
            served[order.staff_id][item.name] += item.qty
    workers = []
    for member in members:
        parts = presence.get(member.id, [])
        if not parts and not order_count[member.id]:
            continue
        workers.append(
            ss.WorkerDay(
                staff_id=str(member.id),
                display_name=member.display_name,
                role_label=member.role_label,
                method=member.method,  # type: ignore[arg-type]
                first_seen=min((i.start for _, i in parts), default=None),
                last_seen=max((i.end for _, i in parts), default=None),
                minutes=area_minutes(parts),
                orders=order_count[member.id],
                items=item_counts(served[member.id]),
                total_items=sum(served[member.id].values()),
            )
        )
    return ss.StaffReport(
        server_time=now,
        venue_id=venue.id,
        day=day,
        is_sample=venue.is_sample,
        coverage=ss.CoverageOut(
            open_min=round(cover.open_min),
            covered_min=round(cover.covered_min),
            share=round(cover.share, 3) if cover.share is not None else None,
            gaps=[ss.GapOut(start=g.start, end=g.end, minutes=round(g.minutes)) for g in cover.gaps],
        ),
        queue_alerts=[ss.QueueAlertOut(start=a.start, end=a.end, peak=a.peak) for a in queue_alerts(points)],
        workers=workers,
    )


def sheet(session: Session, venue: models.Canteen, member: StaffMember, now: datetime, kept_days: int) -> ss.StaffSheet:
    tz = tz_of(venue)
    today = now.astimezone(tz).date()
    days = []
    for offset in range(SHEET_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        start, end = day_bounds(day, tz)
        parts = presence_between(session, [member.id], start, end, now).get(member.id, [])
        orders = [o for o in orders_between(session, venue.id, start, end) if o.staff_id == member.id]
        items = items_of(session, [o.id for o in orders])
        days.append(
            ss.SheetDay(
                day=day, minutes=area_minutes(parts), items=sum(i.qty for group in items.values() for i in group)
            )
        )
    has_face = bool(template_ids(session, [member.id]))
    return ss.StaffSheet(
        server_time=now, staff=staff_out(member, has_face), venue_name=venue.name, days=days, kept_days=kept_days
    )


def import_till(
    session: Session, venue: models.Canteen, payload: ss.TillImportIn, now: datetime
) -> ss.TillImportResult:
    parsed = parse_csv(payload.csv, tz_of(venue))
    refs = [o.order_ref for o in parsed.orders]
    existing = set(
        session.scalars(
            select(TillOrder.order_ref).where(TillOrder.venue_id == venue.id, TillOrder.order_ref.in_(refs))
        )
    )
    codes = {m.till_code: m for m in venue_staff(session, venue.id) if m.till_code}
    cashiers = sorted({o.cashier for o in parsed.orders if o.cashier})
    fresh = [o for o in parsed.orders if o.order_ref not in existing]
    saved = not payload.dry_run and not parsed.errors
    if saved:
        for order in fresh:
            member = codes.get(order.cashier or "")
            row = TillOrder(
                venue_id=venue.id,
                order_ref=order.order_ref,
                at=order.at,
                cashier_code=order.cashier,
                staff_id=member.id if member else None,
                total=order.total,
            )
            session.add(row)
            session.flush()
            session.add_all(
                TillItem(order_id=row.id, name=line.name, qty=line.qty, unit_price=line.unit_price)
                for line in order.lines
            )
    return ss.TillImportResult(
        server_time=now,
        rows=parsed.rows,
        orders=len(parsed.orders),
        new_orders=len(fresh),
        duplicates=len(parsed.orders) - len(fresh),
        errors=parsed.errors,
        matched_cashiers=[c for c in cashiers if c in codes],
        unmatched_cashiers=[c for c in cashiers if c not in codes],
        saved=saved,
    )


def sales(session: Session, venue: models.Canteen, day: date, now: datetime) -> ss.SalesDay:
    tz = tz_of(venue)
    start, end = day_bounds(day, tz)
    orders = orders_between(session, venue.id, start, end)
    items = items_of(session, [o.id for o in orders])
    names = {m.id: m.display_name for m in venue_staff(session, venue.id)}
    hours: Counter[int] = Counter(o.at.astimezone(tz).hour for o in orders)
    top: Counter[str] = Counter()
    by_cashier: dict[str, Counter[str]] = defaultdict(Counter)
    cashier_orders: Counter[str] = Counter()
    cashier_staff: dict[str, uuid.UUID | None] = {}
    revenue = Decimal(0)
    for order in orders:
        code = order.cashier_code or "unknown"
        cashier_orders[code] += 1
        cashier_staff.setdefault(code, order.staff_id)
        revenue += Decimal(order.total)
        for item in items[order.id]:
            top[item.name] += item.qty
            by_cashier[code][item.name] += item.qty
    return ss.SalesDay(
        server_time=now,
        venue_id=venue.id,
        day=day,
        is_sample=venue.is_sample,
        orders=len(orders),
        items=sum(top.values()),
        revenue=float(revenue),
        average_order=round(float(revenue) / len(orders), 2) if orders else None,
        by_hour=[ss.HourOrders(hour=h, orders=hours.get(h, 0)) for h in range(24)],
        by_cashier=[
            ss.CashierItems(
                cashier=code,
                staff_id=str(cashier_staff[code]) if cashier_staff.get(code) else None,
                staff_name=names.get(cashier_staff[code]) if cashier_staff.get(code) else None,
                items=item_counts(by_cashier[code]),
                total_items=sum(by_cashier[code].values()),
                orders=cashier_orders[code],
            )
            for code in sorted(cashier_orders)
        ],
        top_items=item_counts(top)[:10],
    )


def live_signature(token_hash: str, device_id: str, expires: int) -> str:
    return hmac.new(token_hash.encode(), f"{device_id}:{expires}".encode(), hashlib.sha256).hexdigest()


def live_link(device: models.Device, now: datetime, real_now: datetime) -> ss.LiveLink:
    base = (device.config or {}).get("stream_url")
    if not base or not device.token_hash:
        raise conflict("This camera is not streaming. Start the worker with --stream-port on the café computer.")
    expires_at = real_now + LIVE_LINK_TTL
    expires = int(expires_at.timestamp())
    query = urlencode({"exp": expires, "sig": live_signature(device.token_hash, device.id, expires)})
    return ss.LiveLink(server_time=now, device_id=device.id, url=f"{base}?{query}", expires_at=expires_at)


def audit_entries(session: Session, organization_id: str, action: str, now: datetime, limit: int) -> ss.AuditList:
    rows = session.execute(
        select(models.AuditLog, models.User.display_name)
        .join(models.User, models.User.id == models.AuditLog.actor_user_id)
        .where(models.AuditLog.action == action, models.User.organization_id == organization_id)
        .order_by(models.AuditLog.at.desc())
        .limit(limit)
    )
    return ss.AuditList(
        server_time=now,
        items=[ss.AuditEntry(at=a.at, actor=name, action=a.action, entity_id=a.entity_id) for a, name in rows],
    )


def templates_for(session: Session, settings: Settings, device: models.Device, now: datetime) -> ss.StaffTemplates:
    try:
        vault = vault_for(settings)
    except TemplatesUnavailable:
        vault = None
    members = [m for m in venue_staff(session, device.canteen_id) if m.active and m.consent_at is not None]
    sealed = {
        t.staff_id: t.sealed
        for t in session.scalars(select(FaceTemplate).where(FaceTemplate.staff_id.in_([m.id for m in members])))
    }
    staff = []
    for member in members:
        if device.kind == "simulator":
            staff.append(
                ss.DeviceStaff(
                    staff_id=str(member.id),
                    display_name=member.display_name,
                    method=member.method,  # type: ignore[arg-type]
                    badge_code=member.badge_code,
                    template=None,
                )
            )
            continue
        template = None
        if member.method == "face" and vault is not None and member.id in sealed:
            try:
                template = vault.open(sealed[member.id])
            except TemplatesUnavailable:
                template = None
        if member.method == "badge" and member.badge_code is None:
            continue
        if member.method == "face" and template is None:
            continue
        staff.append(
            ss.DeviceStaff(
                staff_id=str(member.id),
                display_name=member.display_name,
                method=member.method,  # type: ignore[arg-type]
                badge_code=member.badge_code if member.method == "badge" else None,
                template=template,
            )
        )
    return ss.StaffTemplates(server_time=now, device_id=device.id, faces_enabled=vault is not None, staff=staff)


def accept_staff(
    session: Session, device: models.Device, payload: ss.StaffSnapshotIn, shift: timedelta, simulated: bool
) -> tuple[int, bool]:
    captured_at = payload.captured_at + shift
    members = {str(m.id): m for m in venue_staff(session, device.canteen_id) if m.active and m.consent_at is not None}
    unknown = sorted({p.staff_id for p in payload.presence} - set(members))
    if unknown:
        raise invalid("Presence names workers who are not enrolled at this venue.", staff_ids=unknown)
    stored = 0
    for item in payload.presence:
        staff_id = members[item.staff_id].id
        if item.ended_at is not None and item.ended_at < item.started_at:
            raise invalid("ended_at is before started_at.", staff_id=item.staff_id)
        started_at = item.started_at + shift
        ended_at = item.ended_at + shift if item.ended_at is not None else None
        row = session.scalar(
            select(StaffPresence).where(
                StaffPresence.staff_id == staff_id,
                StaffPresence.area == item.area,
                StaffPresence.started_at == started_at,
            )
        )
        if row is None:
            if ended_at is None:
                session.execute(
                    delete(StaffPresence).where(
                        StaffPresence.staff_id == staff_id,
                        StaffPresence.area == item.area,
                        StaffPresence.ended_at.is_(None),
                    )
                )
            row = StaffPresence(staff_id=staff_id, area=item.area, started_at=started_at, is_simulated=simulated)
            session.add(row)
        row.ended_at = ended_at
        stored += 1
    if payload.queue is not None or payload.counter is not None:
        session.add(
            QueueReading(
                venue_id=device.canteen_id,
                at=captured_at,
                people=payload.queue.people if payload.queue is not None else None,
                counter_people=payload.counter.people if payload.counter is not None else None,
                is_simulated=simulated,
            )
        )
    return stored, payload.queue is not None


def purge_staff_data(session: Session, now: datetime) -> int:
    removed = 0
    for org in session.scalars(select(models.Organization).where(models.Organization.kind == "business")):
        cutoff = now - timedelta(days=org.staff_retention_days)
        venue_ids = select(models.Canteen.id).where(models.Canteen.organization_id == org.id)
        staff_ids = select(StaffMember.id).where(StaffMember.venue_id.in_(venue_ids))
        removed += (
            session.execute(
                delete(StaffPresence).where(StaffPresence.staff_id.in_(staff_ids), StaffPresence.ended_at < cutoff)
            ).rowcount
            or 0
        )  # type: ignore[attr-defined]
        removed += (
            session.execute(
                delete(QueueReading).where(QueueReading.venue_id.in_(venue_ids), QueueReading.at < cutoff)
            ).rowcount
            or 0
        )  # type: ignore[attr-defined]
    return removed


def local_day(venue: models.Canteen, now: datetime, day: date | None) -> date:
    return day or now.astimezone(tz_of(venue)).date()
