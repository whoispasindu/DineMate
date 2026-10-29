from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas import MealPeriod, Schema, Timestamped

AlertFrom = Literal["busy", "crowded", "near_capacity"]
PolygonType = Literal["seating", "queue", "walkway", "ignore"]
ZoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Coordinate = Annotated[float, Field(ge=0, le=1)]


class MealSlot(Schema):
    weekday: int = Field(ge=0, le=6)
    period: MealPeriod
    starts: time
    ends: time


class MealOverride(Schema):
    date: date
    period: MealPeriod | None = None
    is_cancelled: bool = False
    starts: time | None = None
    ends: time | None = None
    reason: Reason | None = None


class MealScheduleIn(Schema):
    canteen_id: str | None = None
    weekly: list[MealSlot] | None = Field(max_length=21)
    overrides: list[MealOverride] = Field(max_length=120)


class MealScheduleSet(Timestamped):
    canteen_id: str | None
    canteen_name: str
    uses_campus_weekly: bool
    weekly: list[MealSlot]
    campus_weekly: list[MealSlot]
    overrides: list[MealOverride]
    can_edit: bool


class ThresholdValues(Schema):
    busy_pct: float = Field(gt=0, lt=100)
    crowded_pct: float = Field(gt=0, lt=100)
    near_capacity_pct: float = Field(gt=0, le=100)
    hysteresis_pct: float = Field(ge=0, le=20)
    dwell_seconds: int = Field(ge=0, le=1800)
    alert_from: AlertFrom


class ZoneThresholds(Schema):
    zone_id: str
    zone_name: str
    canteen_id: str
    canteen_name: str
    capacity: int
    is_monitored: bool
    is_default: bool
    values: ThresholdValues


class ThresholdList(Timestamped):
    defaults: ThresholdValues
    items: list[ZoneThresholds]


class ThresholdResult(Timestamped):
    item: ZoneThresholds


class LayoutPolygon(Schema):
    type: PolygonType
    zone_id: str | None = None
    points: list[tuple[Coordinate, Coordinate]] = Field(min_length=3, max_length=32)


class EditableZone(Schema):
    id: str
    name: str
    capacity: int
    is_active: bool
    is_monitored: bool


class LayoutVersion(Schema):
    version: int
    created_at: datetime
    is_current: bool
    seating_zones: int


class DeviceLayout(Timestamped):
    device_id: str
    canteen_id: str
    canteen_name: str
    kind: Literal["camera", "simulator"]
    version: int | None
    polygons: list[LayoutPolygon]
    zones: list[EditableZone]
    history: list[LayoutVersion]


class LayoutIn(Schema):
    base_version: int | None
    polygons: list[LayoutPolygon] = Field(max_length=24)


class RollbackIn(Schema):
    version: int = Field(ge=1)


class ManagedDevice(Schema):
    id: str
    kind: Literal["camera", "simulator"]
    canteen_id: str
    canteen_name: str
    layout_version: int | None
    last_heartbeat_at: datetime | None
    is_enabled: bool


class ManagedDeviceList(Timestamped):
    items: list[ManagedDevice]


class ZonePatch(Schema):
    name: ZoneName | None = None
    capacity: int | None = Field(default=None, ge=1, le=500)
    is_active: bool | None = None


class ZoneIn(Schema):
    name: ZoneName
    capacity: int = Field(ge=1, le=500)


class ZoneResult(Timestamped):
    zone: EditableZone
