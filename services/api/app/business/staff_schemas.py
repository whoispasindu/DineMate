from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from app.schemas import Schema, Timestamped

StaffMethod = Literal["face", "badge"]
WorkAreaName = Literal["counter", "kitchen", "floor"]


class StaffOut(Schema):
    id: str
    display_name: str
    role_label: str
    method: StaffMethod
    badge_code: int | None
    till_code: str | None
    consent_at: datetime | None
    consent_version: str | None
    has_template: bool
    active: bool
    is_sample: bool


class StaffList(Timestamped):
    venue_id: str
    items: list[StaffOut]


class StaffResult(Timestamped):
    staff: StaffOut


class StaffIn(Schema):
    display_name: str = Field(min_length=1, max_length=40)
    role_label: str = Field(default="", max_length=40)
    method: StaffMethod = "badge"
    badge_code: int | None = Field(default=None, ge=0, le=249)
    till_code: str | None = Field(default=None, min_length=1, max_length=20)


class StaffPatch(Schema):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    role_label: str | None = Field(default=None, max_length=40)
    method: StaffMethod | None = None
    badge_code: int | None = Field(default=None, ge=0, le=249)
    till_code: str | None = Field(default=None, max_length=20)
    active: bool | None = None


class ConsentIn(Schema):
    version: str = Field(min_length=1, max_length=40)
    signed_on: date


class FaceIn(Schema):
    template: list[float] = Field(min_length=128, max_length=128)


class Removed(Timestamped):
    staff_id: str


class GapOut(Schema):
    start: datetime
    end: datetime
    minutes: int


class QueueAlertOut(Schema):
    start: datetime
    end: datetime
    peak: int


class CoverageOut(Schema):
    open_min: int
    covered_min: int
    share: float | None
    gaps: list[GapOut]


class AreaMinutes(Schema):
    counter: int
    kitchen: int
    floor: int


class ItemCount(Schema):
    name: str
    qty: int


class WorkerDay(Schema):
    staff_id: str
    display_name: str
    role_label: str
    method: StaffMethod
    first_seen: datetime | None
    last_seen: datetime | None
    minutes: AreaMinutes
    orders: int
    items: list[ItemCount]
    total_items: int


class StaffReport(Timestamped):
    venue_id: str
    day: date
    is_sample: bool
    coverage: CoverageOut
    queue_alerts: list[QueueAlertOut]
    workers: list[WorkerDay]


class SheetDay(Schema):
    day: date
    minutes: AreaMinutes
    items: int


class StaffSheet(Timestamped):
    staff: StaffOut
    venue_name: str
    days: list[SheetDay]
    kept_days: int


class TillImportIn(Schema):
    csv: str = Field(min_length=1, max_length=5_000_000)
    dry_run: bool = False


class TillImportResult(Timestamped):
    rows: int
    orders: int
    new_orders: int
    duplicates: int
    errors: list[str]
    matched_cashiers: list[str]
    unmatched_cashiers: list[str]
    saved: bool


class CashierItems(Schema):
    cashier: str
    staff_id: str | None
    staff_name: str | None
    items: list[ItemCount]
    total_items: int
    orders: int


class HourOrders(Schema):
    hour: int
    orders: int


class SalesDay(Timestamped):
    venue_id: str
    day: date
    is_sample: bool
    orders: int
    items: int
    revenue: float
    average_order: float | None
    by_hour: list[HourOrders]
    by_cashier: list[CashierItems]
    top_items: list[ItemCount]


class LiveLink(Timestamped):
    device_id: str
    url: str
    expires_at: datetime


class AuditEntry(Schema):
    at: datetime
    actor: str
    action: str
    entity_id: str


class AuditList(Timestamped):
    items: list[AuditEntry]


class DeviceStaff(Schema):
    staff_id: str
    display_name: str
    method: StaffMethod
    badge_code: int | None
    template: list[float] | None


class StaffTemplates(Timestamped):
    device_id: str
    faces_enabled: bool
    staff: list[DeviceStaff]


class PresenceIn(Schema):
    staff_id: str
    area: WorkAreaName
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None


class QueueIn(Schema):
    people: int = Field(ge=0, le=500)


class StaffSnapshotIn(Schema):
    captured_at: AwareDatetime
    presence: list[PresenceIn] = Field(default_factory=list, max_length=200)
    queue: QueueIn | None = None


class StaffAccepted(Timestamped):
    device_id: str
    presence: int
    queue: bool
