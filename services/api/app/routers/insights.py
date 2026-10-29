import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app import models
from app.core.deps import NowDep, SessionDep
from app.core.errors import NOT_FOUND_RESPONSE, ApiError, not_found
from app.schemas_insights import (
    Bucket,
    Excluded,
    HistoryPointOut,
    Recommendation,
    RecommendationResult,
    ZoneHistory,
)
from app.services.history import BUCKETS, zone_history
from app.services.occupancy import rank_alternatives
from app.services.views import load_bundles

router = APIRouter(tags=["insights"])

DEFAULT_RANGE = timedelta(hours=2)
MAX_RANGE = timedelta(days=7)
NO_ALTERNATIVE = "No reliable alternative right now."


@router.get("/zones/{zone_id}/occupancy/history", response_model=ZoneHistory, responses=NOT_FOUND_RESPONSE)
def get_zone_history(
    zone_id: str,
    session: SessionDep,
    now: NowDep,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    bucket: Bucket = "5m",
) -> ZoneHistory:
    try:
        zone = session.get(models.SeatingZone, uuid.UUID(zone_id))
    except ValueError:
        zone = None
    if zone is None:
        raise not_found("Zone", zone_id)
    end = end or now
    start = start or end - DEFAULT_RANGE
    if start.tzinfo is None or end.tzinfo is None:
        raise ApiError(422, "validation_error", "from and to need a time zone.")
    if not timedelta(0) < end - start <= MAX_RANGE:
        raise ApiError(422, "validation_error", "from must be before to, and the range at most 7 days.")
    points = zone_history(session, zone.id, start, end, BUCKETS[bucket])
    simulated = session.scalar(
        select(models.OccupancyReading.id)
        .where(
            models.OccupancyReading.zone_id == zone.id,
            models.OccupancyReading.captured_at >= start,
            models.OccupancyReading.captured_at < end,
            models.OccupancyReading.is_simulated,
        )
        .limit(1)
    )
    return ZoneHistory(
        server_time=now,
        zone_id=str(zone.id),
        zone_name=zone.name,
        canteen_id=zone.canteen_id,
        capacity=zone.capacity,
        bucket=bucket,
        is_simulated=simulated is not None,
        points=[HistoryPointOut(t=p.t, mean=p.mean, low=p.low, high=p.high, samples=p.samples) for p in points],
    )


def _walks_from(session: SessionDep, from_canteen: str | None) -> dict[str, int]:
    if from_canteen is None:
        return {}
    rows = session.execute(
        select(models.WalkingTime.to_canteen_id, models.WalkingTime.minutes).where(
            models.WalkingTime.from_canteen_id == from_canteen
        )
    )
    return {to_id: minutes for to_id, minutes in rows}


@router.get("/recommendations", response_model=RecommendationResult, responses=NOT_FOUND_RESPONSE)
def get_recommendation(session: SessionDep, now: NowDep, from_canteen: str | None = None) -> RecommendationResult:
    bundles = load_bundles(session, now)
    if from_canteen is not None and all(b.canteen.id != from_canteen for b in bundles):
        raise not_found("Canteen", from_canteen)
    others = {b.canteen.id: b for b in bundles if b.canteen.id != from_canteen}
    walks = _walks_from(session, from_canteen)
    ranked, excluded = rank_alternatives([(cid, b.occupancy) for cid, b in others.items()], walks)
    recommendation = None
    if ranked:
        best = others[ranked[0]]
        o = best.occupancy
        recommendation = Recommendation(
            canteen_id=best.canteen.id,
            name=best.canteen.name,
            level=o.level,
            free_about=o.free_about,
            available_range=o.free_range or (0, 0),
            walk_minutes=walks.get(best.canteen.id),
            reason="Lower crowding with live data" if from_canteen else "Most seats free with live data",
        )
    return RecommendationResult(
        server_time=now,
        from_canteen_id=from_canteen,
        recommendation=recommendation,
        message=None if recommendation else NO_ALTERNATIVE,
        excluded=[Excluded(canteen_id=cid, name=others[cid].canteen.name, reason=r) for cid, r in excluded.items()],
    )
