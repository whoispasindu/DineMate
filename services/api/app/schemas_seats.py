from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from app.schemas import Freshness, Schema, Timestamped

SeatStateName = Literal["free", "occupied", "held", "unknown"]


class SeatIn(Schema):
    seat_id: str = Field(min_length=1, max_length=40)
    zone_id: str
    state: SeatStateName
    for_s: float = Field(ge=0, le=7 * 24 * 3600)
    free_soon: bool = False


class ZoneSeatsIn(Schema):
    zone_id: str
    free: int = Field(ge=0, le=500)
    occupied: int = Field(ge=0, le=500)
    held: int = Field(ge=0, le=500)
    unknown: int = Field(ge=0, le=500)
    free_soon: int = Field(default=0, ge=0, le=500)
    standing: int = Field(default=0, ge=0, le=1000)
    crowded: bool = False


class SeatSnapshotIn(Schema):
    captured_at: AwareDatetime
    zones: list[ZoneSeatsIn] = Field(min_length=1, max_length=50)
    seats: list[SeatIn] = Field(default_factory=list, max_length=1000)


class SeatsAccepted(Timestamped):
    device_id: str
    zones: int
    seats: int
    changed: int


class ZoneSeats(Schema):
    zone_id: str
    name: str
    freshness: Freshness
    seats: int
    free: int | None
    occupied: int | None
    held: int | None
    unknown: int | None
    free_soon: int | None
    standing: int | None
    crowded: bool
    updated_at: datetime | None


class CanteenSeats(Timestamped):
    canteen_id: str
    zones: list[ZoneSeats]
    held: int
    free_soon: int
    crowded_zones: int


class CanteenSeatTotals(Schema):
    canteen_id: str
    zones_with_seats: int
    held: int
    free_soon: int
    crowded_zones: int


class SeatOverview(Timestamped):
    items: list[CanteenSeatTotals]


class SeatDetail(Schema):
    seat_id: str
    x: float
    y: float
    state: SeatStateName
    since: datetime | None
    free_soon: bool


class ZoneSeatMap(Timestamped):
    zone_id: str
    name: str
    freshness: Freshness
    seats: list[SeatDetail]
