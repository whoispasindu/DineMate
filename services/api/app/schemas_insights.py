from datetime import datetime
from typing import Literal

from app.schemas import CrowdLevel, FreeRange, Schema, Timestamped

Bucket = Literal["5m", "10m", "15m", "1h"]


class HistoryPointOut(Schema):
    t: datetime
    mean: float
    low: int
    high: int
    samples: int


class ZoneHistory(Timestamped):
    zone_id: str
    zone_name: str
    canteen_id: str
    capacity: int
    bucket: Bucket
    is_simulated: bool
    points: list[HistoryPointOut]


class Recommendation(Schema):
    canteen_id: str
    name: str
    level: CrowdLevel
    free_about: int | None
    available_range: FreeRange
    walk_minutes: int | None
    reason: str


class Excluded(Schema):
    canteen_id: str
    name: str
    reason: Literal["no_live_data", "too_crowded"]


class RecommendationResult(Timestamped):
    from_canteen_id: str | None
    recommendation: Recommendation | None
    message: str | None
    excluded: list[Excluded]
