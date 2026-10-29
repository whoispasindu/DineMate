from datetime import datetime
from typing import Literal

from app.schemas import CrowdLevel, FreeRange, Freshness, SafetyEvent, SafetyStatus, Schema, Timestamped

NoticeKind = Literal["crowding", "data_unavailable", "sold_out", "shop_closing", "meal_starting"]


class StaffAlert(Schema):
    id: str
    type: Literal["crowding", "sensor_offline", "data_stale"]
    level: CrowdLevel | None
    title: str
    detail: str | None
    status: Literal["open", "acknowledged", "suspended", "resolved"]
    opened_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None


class StaffAlertList(Timestamped):
    items: list[StaffAlert]


class StaffAlertResult(StaffAlert):
    server_time: datetime


class ConsoleZone(Schema):
    zone_id: str
    name: str
    canteen_name: str
    capacity: int
    freshness: Freshness
    level: CrowdLevel
    occupied: int | None
    occupied_range: FreeRange | None
    updated_at: datetime | None


class DeviceHealth(Schema):
    id: str
    where: str
    status: Literal["ok", "not_reporting", "offline"]
    fps: float | None
    latency_ms: int | None
    last_seen_at: datetime | None


class OccupancyPoint(Schema):
    at: datetime
    percent: int
    is_forecast: bool


class OccupancyToday(Schema):
    canteen_name: str
    points: list[OccupancyPoint]


class SafetySource(Schema):
    name: str
    online: bool
    last_heartbeat_at: datetime | None


class ConsoleSafety(Schema):
    simulation_mode: bool
    events: list[SafetyEvent]
    source: SafetySource
    real_integration_connected: bool


class ConsoleOverview(Timestamped):
    is_sample: bool
    zones: list[ConsoleZone]
    alerts: list[StaffAlert]
    devices: list[DeviceHealth]
    occupancy_today: OccupancyToday
    safety: ConsoleSafety


class RelatedCanteen(Schema):
    id: str
    name: str


class Notice(Schema):
    id: str
    kind: NoticeKind
    title: str
    body: str
    context: str
    at: datetime
    related_canteen: RelatedCanteen | None


class AlertFeed(Timestamped):
    safety: SafetyStatus
    notices: list[Notice]
