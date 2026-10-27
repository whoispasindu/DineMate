from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Freshness = Literal["live", "stale", "unavailable"]
CrowdLevel = Literal["normal", "busy", "crowded", "near_capacity", "unknown"]

STALE_AFTER_S = 120
UNAVAILABLE_AFTER_S = 600


@dataclass(frozen=True)
class Thresholds:
    busy: float = 60
    crowded: float = 80
    near_capacity: float = 95


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class Reading:
    captured_at: datetime
    occupied: int
    low: int
    high: int
    capacity: int


@dataclass(frozen=True)
class ZoneView:
    zone_id: str
    name: str
    capacity: int
    freshness: Freshness
    level: CrowdLevel
    percent: int | None
    free_about: int | None
    free_range: tuple[int, int] | None
    updated_at: datetime | None


@dataclass(frozen=True)
class CanteenOccupancy:
    level: CrowdLevel
    freshness: Freshness
    percent: int | None
    free_about: int | None
    free_range: tuple[int, int] | None
    monitored_capacity: int
    zones_live: int
    zones_total: int
    updated_at: datetime | None


def freshness_for(captured_at: datetime | None, now: datetime) -> Freshness:
    if captured_at is None:
        return "unavailable"
    age = (now - captured_at).total_seconds()
    if age <= STALE_AFTER_S:
        return "live"
    if age <= UNAVAILABLE_AFTER_S:
        return "stale"
    return "unavailable"


def level_for(percent: float, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> CrowdLevel:
    if percent >= thresholds.near_capacity:
        return "near_capacity"
    if percent >= thresholds.crowded:
        return "crowded"
    if percent >= thresholds.busy:
        return "busy"
    return "normal"


def zone_view(zone_id: str, name: str, capacity: int, reading: Reading | None, now: datetime) -> ZoneView:
    freshness = freshness_for(reading.captured_at if reading else None, now)
    if reading is None or freshness == "unavailable":
        return ZoneView(
            zone_id=zone_id,
            name=name,
            capacity=capacity,
            freshness="unavailable",
            level="unknown",
            percent=None,
            free_about=None,
            free_range=None,
            updated_at=reading.captured_at if reading else None,
        )
    cap = reading.capacity
    occupied = min(reading.occupied, cap)
    percent = round(occupied / cap * 100)
    return ZoneView(
        zone_id=zone_id,
        name=name,
        capacity=cap,
        freshness=freshness,
        level=level_for(percent) if freshness == "live" else "unknown",
        percent=percent,
        free_about=cap - occupied,
        free_range=(max(0, cap - reading.high), max(0, cap - reading.low)),
        updated_at=reading.captured_at,
    )


def canteen_occupancy(zones: list[ZoneView]) -> CanteenOccupancy:
    counted = [z for z in zones if z.free_range is not None and z.free_about is not None]
    live = [z for z in zones if z.freshness == "live"]
    capacity = sum(z.capacity for z in counted)
    free = sum(z.free_about or 0 for z in counted)
    low = sum(z.free_range[0] for z in counted if z.free_range)
    high = sum(z.free_range[1] for z in counted if z.free_range)
    percent = round((capacity - free) / capacity * 100) if capacity > 0 else None
    freshness: Freshness = "live" if live else "stale" if counted else "unavailable"
    stamps = [z.updated_at for z in zones if z.updated_at is not None]
    return CanteenOccupancy(
        level=level_for(percent) if percent is not None and freshness == "live" else "unknown",
        freshness=freshness,
        percent=percent,
        free_about=free if counted else None,
        free_range=(low, high) if counted else None,
        monitored_capacity=capacity,
        zones_live=len(live),
        zones_total=len(zones),
        updated_at=max(stamps) if stamps else None,
    )


def best_candidate(candidates: list[tuple[str, CanteenOccupancy]]) -> str | None:
    eligible = [
        (canteen_id, o)
        for canteen_id, o in candidates
        if o.freshness == "live" and o.level in ("normal", "busy") and o.free_range is not None
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda item: item[1].free_range[0] if item[1].free_range else 0)[0]
