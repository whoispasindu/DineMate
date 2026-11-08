from typing import Literal

from pydantic import AwareDatetime, Field

from app.schemas import Schema, Timestamped

Point = tuple[float, float]


class ConfigSeat(Schema):
    seat_id: str
    x: float
    y: float


class ConfigZone(Schema):
    zone_id: str
    name: str
    capacity: int
    points: list[Point]
    seats: list[ConfigSeat] = Field(default_factory=list)


class IgnoreArea(Schema):
    type: Literal["queue", "walkway", "ignore"]
    points: list[Point]


class WorkerSettings(Schema):
    post_every_s: float
    smoothing_s: float
    dwell_s: float
    fps: float
    min_confidence: float
    seated_ratio: float
    h_stand_a: float | None
    h_stand_b: float | None
    clear_s: float = 30.0
    held_after_s: float = 20.0
    hidden_free_s: float = 10.0
    hidden_hold_s: float = 120.0
    abandoned_s: float = 300.0
    seat_radius: float = 0.06
    objects_every_s: float = 5.0


class SimulationProfile(Schema):
    base: int
    below: int
    above: int


class DeviceConfig(Timestamped):
    device_id: str
    kind: Literal["camera", "simulator"]
    canteen_id: str
    layout_version: int | None
    zones: list[ConfigZone]
    ignore: list[IgnoreArea]
    settings: WorkerSettings
    simulation: dict[str, SimulationProfile] | None


class ZoneReadingIn(Schema):
    zone_id: str
    estimated_occupied: int = Field(ge=0)
    occupied_low: int | None = Field(default=None, ge=0)
    occupied_high: int | None = Field(default=None, ge=0)
    confidence: Literal["high", "medium", "low"] = "medium"
    samples: int | None = Field(default=None, ge=0)


class OccupancyIn(Schema):
    captured_at: AwareDatetime
    readings: list[ZoneReadingIn] = Field(min_length=1, max_length=50)


class OccupancyAccepted(Timestamped):
    device_id: str
    accepted: int


class HeartbeatIn(Schema):
    status: Literal["ok", "degraded", "error"]
    fps: float | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    stream_ok: bool = True
    message: str | None = Field(default=None, max_length=500)


class HeartbeatAccepted(Timestamped):
    device_id: str
