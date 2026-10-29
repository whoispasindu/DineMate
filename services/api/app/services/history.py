import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, func, literal, literal_column, select
from sqlalchemy.orm import Session

from app import models
from app.services.forecast import SLOT, Evaluation, Prediction, Series, evaluate, predict, slot_start

BUCKETS = {
    "5m": timedelta(minutes=5),
    "10m": timedelta(minutes=10),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
}
ORIGIN = datetime(2000, 1, 1, tzinfo=UTC)
LOOKBACK = timedelta(days=35)
CACHE_FOR = timedelta(minutes=10)


@dataclass(frozen=True)
class HistoryPoint:
    t: datetime
    mean: float
    low: int
    high: int
    samples: int


def _bin(bucket: timedelta) -> ColumnElement[datetime]:
    seconds = int(bucket.total_seconds())
    return func.date_bin(
        literal_column(f"interval '{seconds} seconds'"), models.OccupancyReading.captured_at, literal(ORIGIN)
    )


def zone_history(
    session: Session, zone_id: uuid.UUID, start: datetime, end: datetime, bucket: timedelta
) -> list[HistoryPoint]:
    r = models.OccupancyReading
    t = _bin(bucket).label("t")
    rows = session.execute(
        select(t, func.avg(r.estimated_occupied), func.avg(r.occupied_low), func.avg(r.occupied_high), func.count())
        .where(r.zone_id == zone_id, r.captured_at >= start, r.captured_at < end)
        .group_by(t)
        .order_by(t)
    )
    return [
        HistoryPoint(row[0], round(float(row[1]), 1), round(float(row[2])), round(float(row[3])), row[4])
        for row in rows
    ]


def canteen_series(session: Session, zone_ids: list[uuid.UUID], start: datetime, end: datetime) -> Series:
    if not zone_ids:
        return Series({})
    r = models.OccupancyReading
    t = _bin(SLOT).label("t")
    rows = session.execute(
        select(t, r.zone_id, func.avg(r.estimated_occupied), func.max(r.capacity_snapshot))
        .where(r.zone_id.in_(zone_ids), r.captured_at >= start, r.captured_at < end)
        .group_by(t, r.zone_id)
    )
    slots: dict[datetime, list[tuple[float, int]]] = defaultdict(list)
    for slot, _zone, occupied, capacity in rows:
        slots[slot].append((float(occupied), int(capacity)))
    return Series(
        {slot: sum(o for o, _ in v) / sum(c for _, c in v) * 100 for slot, v in slots.items() if sum(c for _, c in v)}
    )


@dataclass(frozen=True)
class Model:
    series: Series
    evaluation: Evaluation
    built_at: datetime


_cache: dict[tuple[str, tuple[uuid.UUID, ...]], Model] = {}
_lock = threading.Lock()


def canteen_model(session: Session, canteen_id: str, zone_ids: list[uuid.UUID], now: datetime) -> Model:
    key = (canteen_id, tuple(sorted(zone_ids)))
    with _lock:
        cached = _cache.get(key)
    if cached is not None and timedelta(0) <= now - cached.built_at < CACHE_FOR:
        return cached
    series = canteen_series(session, zone_ids, now - LOOKBACK, slot_start(now))
    model = Model(series=series, evaluation=evaluate(series), built_at=now)
    with _lock:
        _cache[key] = model
    return model


def canteen_forecast(
    session: Session, canteen_id: str, zone_ids: list[uuid.UUID], now: datetime, current: float | None
) -> list[Prediction]:
    model = canteen_model(session, canteen_id, zone_ids, now)
    return predict(model.series, now, current, model.evaluation.params)


def clear_cache() -> None:
    with _lock:
        _cache.clear()
