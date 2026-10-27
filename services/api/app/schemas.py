from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CrowdLevel = Literal["normal", "busy", "crowded", "near_capacity", "unknown"]
Freshness = Literal["live", "stale", "unavailable"]
MealPeriod = Literal["breakfast", "lunch", "dinner"]
ShopState = Literal["open", "closes_soon", "closed", "temporarily_closed", "unknown"]
ShopKind = Literal["rice", "kottu", "short_eats", "tea", "noodles", "bakery", "drinks"]
MenuTag = Literal["rice", "kottu", "short_eats", "drinks", "vegetarian"]
FreeRange = tuple[int, int]


class Schema(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Timestamped(Schema):
    server_time: datetime


class WalkTime(Schema):
    from_name: str
    minutes: int


class CanteenSummary(Schema):
    id: str
    name: str
    is_sample: bool
    level: CrowdLevel
    freshness: Freshness
    percent: int | None
    free_about: int | None
    free_range: FreeRange | None
    monitored_capacity: int
    zones_live: int
    zones_total: int
    shops_total: int
    shops_open: int
    walk: WalkTime | None
    updated_at: datetime | None


class CanteenList(Timestamped):
    items: list[CanteenSummary]


class ShopStatus(Schema):
    state: ShopState
    closes_at_local: str | None
    opens_at_local: str | None
    reason: str | None


class Shop(Schema):
    id: str
    name: str
    canteen_id: str
    canteen_name: str
    kind: ShopKind
    is_sample: bool
    status: ShopStatus
    hours_label: str
    menu_updated_at: datetime | None


class ShopList(Timestamped):
    canteen_id: str
    items: list[Shop]


class MenuItem(Schema):
    id: str
    name: str
    price_lkr: float
    tags: list[MenuTag]
    periods: list[MealPeriod]
    is_available: bool


class Menu(Timestamped):
    shop_id: str
    is_sample: bool
    items: list[MenuItem]
    menu_updated_at: datetime | None


class ZoneOccupancy(Schema):
    zone_id: str
    name: str
    capacity: int
    freshness: Freshness
    level: CrowdLevel
    percent: int | None
    free_about: int | None
    free_range: FreeRange | None
    updated_at: datetime | None


class ZoneOccupancyList(Timestamped):
    canteen_id: str
    zones: list[ZoneOccupancy]


class ForecastPoint(Schema):
    at: datetime
    low: int
    high: int


class OpeningHours(Schema):
    opens: str
    closes: str


class CanteenDetail(Timestamped):
    canteen: CanteenSummary
    hours_today: list[OpeningHours]
    zones: list[ZoneOccupancy]
    forecast: list[ForecastPoint]
    shops: list[Shop]


class MealWindow(Schema):
    period: MealPeriod
    starts: datetime
    ends: datetime


class WeekDay(Schema):
    date: str
    weekday: str
    day: int
    kind: Literal["regular", "special", "closed"]
    note: str | None
    is_today: bool


class MealStatus(Timestamped):
    timezone: Literal["Asia/Colombo"]
    is_sample: bool
    state: Literal["active", "upcoming", "none"]
    current: MealWindow | None
    next: MealWindow | None
    today: list[MealWindow]
    week: list[WeekDay]


class BusyPoint(Schema):
    label: str
    percent: int
    is_forecast: bool
    is_now: bool


class BusyToday(Schema):
    canteen_id: str
    canteen_name: str
    points: list[BusyPoint]


class SafetyEvent(Schema):
    id: str
    event_type: str
    title: str
    canteen_name: str | None
    occurred_at: datetime
    is_simulation: bool
    status: Literal["active", "acknowledged", "resolved"]
    source_name: str
    instructions: str


class SafetyStatus(Schema):
    active: bool
    events: list[SafetyEvent]


class BestCanteen(Schema):
    canteen_id: str
    name: str


class StudentSummary(Timestamped):
    best: BestCanteen | None
    canteens: list[CanteenSummary]
    shops_now: list[Shop]
    busy_today: BusyToday | None
    safety: SafetyStatus


class ErrorDetail(Schema):
    code: str
    message: str
    details: dict[str, object] | None


class ErrorResponse(Schema):
    error: ErrorDetail
    request_id: str
