from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from app import models
from app.business import schemas as s
from app.business import service
from app.business.auth import BusinessUser, OwnerUser, venue_for, visible_venues
from app.business.templates import TemplatesUnavailable, vault_for
from app.core.config import Settings, get_settings
from app.core.deps import NowDep, SessionDep
from app.core.errors import not_found
from app.schemas import ErrorResponse
from app.services.audit import record

router = APIRouter(prefix="/business", tags=["business"])

RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("/venues", response_model=s.VenueList, responses=RESPONSES)
def list_venues(user: BusinessUser, session: SessionDep, now: NowDep) -> s.VenueList:
    org = session.get(models.Organization, user.organization_id)
    venues = visible_venues(user, service.org_venues(session, user.organization_id))
    return s.VenueList(
        server_time=now,
        items=[
            s.VenueSummary(
                id=v.id,
                name=v.name,
                organization_name=org.name if org else "",
                is_sample=v.is_sample,
                zones=[s.VenueZone(id=str(z.id), name=z.name) for z in v.zones if z.is_active],
                tables=len(service.venue_tables(session, v.id)),
            )
            for v in venues
        ],
    )


@router.get("/venues/{venue_id}/floor", response_model=s.VenueFloor, responses=RESPONSES)
def get_floor(venue_id: str, user: BusinessUser, session: SessionDep, now: NowDep) -> s.VenueFloor:
    return service.floor(session, venue_for(session, user, venue_id), now)


@router.get("/venues/{venue_id}/customers", response_model=s.CustomerDay, responses=RESPONSES)
def get_customers(
    venue_id: str, user: BusinessUser, session: SessionDep, now: NowDep, day: Annotated[date | None, Query()] = None
) -> s.CustomerDay:
    venue = venue_for(session, user, venue_id)
    return service.customers(session, venue, day or now.astimezone(service.tz_of(venue)).date(), now)


@router.get("/venues/{venue_id}/reports", response_model=s.VenueReport, responses=RESPONSES)
def get_report(
    venue_id: str,
    user: BusinessUser,
    session: SessionDep,
    now: NowDep,
    span: Annotated[Literal["day", "week"], Query(alias="range")] = "week",
) -> s.VenueReport:
    return service.report(session, venue_for(session, user, venue_id), span, now)


@router.get("/venues/{venue_id}/cameras", response_model=s.VenueCameras, responses=RESPONSES)
def get_cameras(venue_id: str, user: BusinessUser, session: SessionDep, now: NowDep) -> s.VenueCameras:
    return service.cameras(session, venue_for(session, user, venue_id), now)


@router.get("/venues/{venue_id}/tables", response_model=s.TableLayout, responses=RESPONSES)
def get_tables(venue_id: str, user: BusinessUser, session: SessionDep, now: NowDep) -> s.TableLayout:
    return service.table_layout(session, venue_for(session, user, venue_id), now)


@router.put("/venues/{venue_id}/tables", response_model=s.TableLayout, responses=RESPONSES)
def put_tables(
    venue_id: str, payload: s.TablesIn, user: BusinessUser, session: SessionDep, now: NowDep, request: Request
) -> s.TableLayout:
    venue = venue_for(session, user, venue_id)
    before, after = service.replace_tables(session, venue, payload)
    record(
        session,
        now,
        "business.tables.replace",
        "venue",
        venue.id,
        user=user,
        before={"tables": before},
        after={"tables": after},
        request=request,
    )
    session.commit()
    return service.table_layout(session, venue, now)


@router.post("/tables/{table_id}/cleared", response_model=s.VenueFloor, responses=RESPONSES)
def mark_cleared(table_id: str, user: BusinessUser, session: SessionDep, now: NowDep, request: Request) -> s.VenueFloor:
    table = service.load_venue_table(session, table_id)
    if table is None:
        raise not_found("Table", table_id)
    venue = venue_for(session, user, table.venue_id)
    table.cleared_at = now
    record(session, now, "business.table.cleared", "venue_table", table_id, user=user, request=request)
    session.commit()
    return service.floor(session, venue, now)


def _faces_enabled(settings: Settings) -> bool:
    try:
        vault_for(settings)
    except TemplatesUnavailable:
        return False
    return True


def _settings(session: SessionDep, user: models.User, settings: Settings, now: NowDep) -> s.BusinessSettings:
    org = session.get(models.Organization, user.organization_id)
    if org is None:
        raise not_found("Organization", user.organization_id)
    return s.BusinessSettings(
        server_time=now,
        organization_id=org.id,
        organization_name=org.name,
        retention_days=org.retention_days,
        staff_retention_days=org.staff_retention_days,
        deployment="cloud" if settings.deployment == "cloud" else "local",
        faces_enabled=_faces_enabled(settings),
    )


@router.get("/settings", response_model=s.BusinessSettings, responses=RESPONSES)
def get_settings_view(
    user: BusinessUser, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)], now: NowDep
) -> s.BusinessSettings:
    return _settings(session, user, settings, now)


@router.patch("/settings", response_model=s.BusinessSettings, responses=RESPONSES)
def patch_settings(
    payload: s.SettingsIn,
    user: OwnerUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    now: NowDep,
    request: Request,
) -> s.BusinessSettings:
    org = session.get(models.Organization, user.organization_id)
    if org is None:
        raise not_found("Organization", user.organization_id)
    before = {"retention_days": org.retention_days, "staff_retention_days": org.staff_retention_days}
    if payload.retention_days is not None:
        org.retention_days = payload.retention_days
    if payload.staff_retention_days is not None:
        org.staff_retention_days = payload.staff_retention_days
    record(
        session,
        now,
        "business.settings.update",
        "organization",
        org.id,
        user=user,
        before=before,
        after={"retention_days": org.retention_days, "staff_retention_days": org.staff_retention_days},
        request=request,
    )
    session.commit()
    return _settings(session, user, settings, now)
