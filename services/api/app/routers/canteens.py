from fastapi import APIRouter

from app import schemas
from app.core.deps import NowDep, SessionDep
from app.core.errors import NOT_FOUND_RESPONSE, not_found
from app.services.views import (
    CanteenBundle,
    bundle_forecast,
    canteen_summary,
    forecast_schema,
    hours_today,
    load_bundles,
    nearest_walks,
    zone_schema,
)

router = APIRouter(tags=["canteens"])


def _one(session: SessionDep, now: NowDep, canteen_id: str) -> CanteenBundle:
    bundles = load_bundles(session, now, canteen_id)
    if not bundles:
        raise not_found("Canteen", canteen_id)
    return bundles[0]


@router.get("/canteens", response_model=schemas.CanteenList)
def list_canteens(session: SessionDep, now: NowDep) -> schemas.CanteenList:
    walks = nearest_walks(session)
    return schemas.CanteenList(server_time=now, items=[canteen_summary(b, walks) for b in load_bundles(session, now)])


@router.get("/canteens/{canteen_id}", response_model=schemas.CanteenDetail, responses=NOT_FOUND_RESPONSE)
def get_canteen(canteen_id: str, session: SessionDep, now: NowDep) -> schemas.CanteenDetail:
    bundle = _one(session, now, canteen_id)
    return schemas.CanteenDetail(
        server_time=now,
        canteen=canteen_summary(bundle, nearest_walks(session)),
        hours_today=hours_today(bundle.canteen, now),
        zones=[zone_schema(z) for z in bundle.zones],
        forecast=forecast_schema(bundle_forecast(session, bundle, now)),
        shops=bundle.shops,
    )


@router.get("/canteens/{canteen_id}/occupancy", response_model=schemas.ZoneOccupancyList, responses=NOT_FOUND_RESPONSE)
def get_canteen_occupancy(canteen_id: str, session: SessionDep, now: NowDep) -> schemas.ZoneOccupancyList:
    bundle = _one(session, now, canteen_id)
    return schemas.ZoneOccupancyList(
        server_time=now, canteen_id=canteen_id, zones=[zone_schema(z) for z in bundle.zones]
    )


@router.get("/canteens/{canteen_id}/shops", response_model=schemas.ShopList, responses=NOT_FOUND_RESPONSE)
def get_canteen_shops(canteen_id: str, session: SessionDep, now: NowDep) -> schemas.ShopList:
    bundle = _one(session, now, canteen_id)
    return schemas.ShopList(server_time=now, canteen_id=canteen_id, items=bundle.shops)
