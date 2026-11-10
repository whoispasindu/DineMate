from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas import Schema, Timestamped

TableStateName = Literal["free", "occupied", "held", "needs_clearing", "unknown"]
TableShape = Literal["round", "rect"]
Unit = Field(ge=0, le=1)


class VenueZone(Schema):
    id: str
    name: str


class VenueSummary(Schema):
    id: str
    name: str
    organization_name: str
    is_sample: bool
    zones: list[VenueZone]
    tables: int


class VenueList(Timestamped):
    items: list[VenueSummary]


class LeaveEstimate(Schema):
    low_min: int
    high_min: int


class FloorTable(Schema):
    id: str
    name: str
    zone_id: str
    zone_name: str
    shape: TableShape
    x: float
    y: float
    w: float
    h: float
    seats: int
    state: TableStateName
    party_size: int
    since: datetime | None
    seated_min: int | None
    plates_left: bool
    estimate: LeaveEstimate | None


class FloorTotals(Schema):
    tables: int
    free: int
    guests_seated: int
    visits_today: int
    avg_stay_today_min: int | None
    turns_today: float
    counter_staff: int | None = None
    queue_people: int | None = None


class VenueFloor(Timestamped):
    venue_id: str
    venue_name: str
    is_sample: bool
    updated_at: datetime | None
    totals: FloorTotals
    tables: list[FloorTable]


class HourCount(Schema):
    hour: int
    visits: int


class TableStay(Schema):
    table_id: str
    name: str
    seats: int
    avg_stay_min: int | None
    turns: int


class CustomerDay(Timestamped):
    venue_id: str
    day: date
    is_sample: bool
    visits: int
    visits_last_week: int
    guests: int
    avg_stay_min: int | None
    median_stay_min: int | None
    turns_per_table: float
    by_hour: list[HourCount]
    by_table: list[TableStay]


class DayTotal(Schema):
    day: date
    visits: int
    guests: int
    avg_stay_min: int | None


class HeatCell(Schema):
    weekday: int
    hour: int
    visits: int


class VenueReport(Timestamped):
    venue_id: str
    range: Literal["day", "week"]
    is_sample: bool
    days: list[DayTotal]
    heat: list[HeatCell]
    heat_days: int


class CameraHealth(Schema):
    id: str
    kind: Literal["camera", "simulator"]
    zones: list[str]
    status: Literal["ok", "not_reporting", "offline"]
    fps: float | None
    last_seen_at: datetime | None
    label: str | None = None
    source_hint: str | None = None
    has_layout: bool = False
    waiting_for_zones: bool = False
    detail: Literal["auto", "standard", "high"] = "auto"


class VenueCameras(Timestamped):
    venue_id: str
    items: list[CameraHealth]


class SeatPoint(Schema):
    seat_id: str
    x: float
    y: float


class LayoutZoneSeats(Schema):
    zone_id: str
    name: str
    seats: list[SeatPoint]


class TableOut(Schema):
    id: str
    name: str
    zone_id: str
    shape: TableShape
    x: float
    y: float
    w: float
    h: float
    seat_ids: list[str]


class TableLayout(Timestamped):
    venue_id: str
    zones: list[LayoutZoneSeats]
    tables: list[TableOut]


class TableIn(Schema):
    id: str | None = None
    name: str = Field(min_length=1, max_length=12)
    zone_id: str
    shape: TableShape = "rect"
    x: float = Unit
    y: float = Unit
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    seat_ids: list[str] = Field(min_length=1, max_length=20)


class TablesIn(Schema):
    tables: list[TableIn] = Field(max_length=200)


class BusinessSettings(Timestamped):
    organization_id: str
    organization_name: str
    retention_days: int
    staff_retention_days: int
    deployment: Literal["local", "cloud"]
    faces_enabled: bool


class SettingsIn(Schema):
    retention_days: int | None = Field(default=None, ge=7, le=730)
    staff_retention_days: int | None = Field(default=None, ge=7, le=365)
