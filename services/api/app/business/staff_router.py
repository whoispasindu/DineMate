from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app import models
from app.business import staff_schemas as ss
from app.business import staff_service as svc
from app.business.auth import BusinessUser, OwnerUser, venue_for
from app.business.router import RESPONSES
from app.business.staff_service import load_staff
from app.core.config import Settings, get_settings
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import DeviceDep, RealNowDep
from app.core.errors import ApiError, not_found
from app.routers.devices import AUTH_RESPONSES, MAX_FUTURE_SKEW
from app.services.audit import record

router = APIRouter(prefix="/business", tags=["business-staff"])
devices = APIRouter(tags=["business-staff"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
STAFF_REPORT_VIEW = "business.staff_report.view"


def staff_for(session: SessionDep, user: models.User, staff_id: str) -> tuple[Any, models.Canteen]:
    member = load_staff(session, staff_id)
    if member is None:
        raise not_found("Staff", staff_id)
    return member, venue_for(session, user, member.venue_id)


def result(session: SessionDep, member: Any, now: datetime) -> ss.StaffResult:
    return ss.StaffResult(server_time=now, staff=svc.staff_out(member, bool(svc.template_ids(session, [member.id]))))


@router.get("/venues/{venue_id}/staff", response_model=ss.StaffList, responses=RESPONSES)
def list_staff(venue_id: str, user: OwnerUser, session: SessionDep, now: NowDep) -> ss.StaffList:
    return svc.list_staff(session, venue_for(session, user, venue_id), now)


@router.post("/venues/{venue_id}/staff", response_model=ss.StaffResult, responses=RESPONSES)
def create_staff(
    venue_id: str, payload: ss.StaffIn, user: OwnerUser, session: SessionDep, now: NowDep, request: Request
) -> ss.StaffResult:
    venue = venue_for(session, user, venue_id)
    member = svc.create_staff(session, venue, payload, now)
    record(
        session,
        now,
        "business.staff.create",
        "staff",
        str(member.id),
        user=user,
        after=payload.model_dump(),
        request=request,
    )
    session.commit()
    return result(session, member, now)


@router.patch("/staff/{staff_id}", response_model=ss.StaffResult, responses=RESPONSES)
def patch_staff(
    staff_id: str, payload: ss.StaffPatch, user: OwnerUser, session: SessionDep, now: NowDep, request: Request
) -> ss.StaffResult:
    member, _ = staff_for(session, user, staff_id)
    before = svc.staff_out(member, False).model_dump(mode="json")
    svc.patch_staff(session, member, payload)
    record(
        session,
        now,
        "business.staff.update",
        "staff",
        staff_id,
        user=user,
        before=before,
        after=payload.model_dump(exclude_unset=True),
        request=request,
    )
    session.commit()
    return result(session, member, now)


@router.post("/staff/{staff_id}/consent", response_model=ss.StaffResult, responses=RESPONSES)
def record_consent(
    staff_id: str, payload: ss.ConsentIn, user: OwnerUser, session: SessionDep, now: NowDep, request: Request
) -> ss.StaffResult:
    member, venue = staff_for(session, user, staff_id)
    signed = datetime.combine(payload.signed_on, datetime.min.time(), tzinfo=svc.tz_of(venue))
    if signed > now:
        raise ApiError(422, "validation_error", "The consent date cannot be in the future.")
    member.consent_at = signed
    member.consent_version = payload.version
    record(
        session,
        now,
        "business.staff.consent",
        "staff",
        staff_id,
        user=user,
        after=payload.model_dump(mode="json"),
        request=request,
    )
    session.commit()
    return result(session, member, now)


@router.delete("/staff/{staff_id}/consent", response_model=ss.StaffResult, responses=RESPONSES)
def withdraw_consent(
    staff_id: str, user: OwnerUser, session: SessionDep, now: NowDep, request: Request
) -> ss.StaffResult:
    member, _ = staff_for(session, user, staff_id)
    svc.withdraw_consent(session, member)
    record(session, now, "business.staff.consent_withdrawn", "staff", staff_id, user=user, request=request)
    session.commit()
    return result(session, member, now)


@router.delete("/staff/{staff_id}", response_model=ss.Removed, responses=RESPONSES)
def remove_staff(staff_id: str, user: OwnerUser, session: SessionDep, now: NowDep, request: Request) -> ss.Removed:
    member, _ = staff_for(session, user, staff_id)
    record(
        session,
        now,
        "business.staff.remove",
        "staff",
        staff_id,
        user=user,
        before={"display_name": member.display_name},
        request=request,
    )
    session.delete(member)
    session.commit()
    return ss.Removed(server_time=now, staff_id=staff_id)


@router.post("/staff/{staff_id}/face", response_model=ss.StaffResult, responses=RESPONSES)
def enrol_face(
    staff_id: str,
    payload: ss.FaceIn,
    user: OwnerUser,
    session: SessionDep,
    settings: SettingsDep,
    now: NowDep,
    request: Request,
) -> ss.StaffResult:
    member, _ = staff_for(session, user, staff_id)
    svc.store_template(session, settings, member, payload.template, now)
    record(session, now, "business.staff.face_enrolled", "staff", staff_id, user=user, request=request)
    session.commit()
    return result(session, member, now)


@router.get("/venues/{venue_id}/staff-report", response_model=ss.StaffReport, responses=RESPONSES)
def staff_report(
    venue_id: str,
    user: OwnerUser,
    session: SessionDep,
    now: NowDep,
    request: Request,
    day: Annotated[date | None, Query()] = None,
) -> ss.StaffReport:
    venue = venue_for(session, user, venue_id)
    chosen = svc.local_day(venue, now, day)
    record(
        session,
        now,
        STAFF_REPORT_VIEW,
        "venue",
        venue.id,
        user=user,
        after={"day": chosen.isoformat()},
        request=request,
    )
    session.commit()
    return svc.report(session, venue, chosen, now)


@router.get("/staff/{staff_id}/sheet", response_model=ss.StaffSheet, responses=RESPONSES)
def staff_sheet(staff_id: str, user: OwnerUser, session: SessionDep, now: NowDep, request: Request) -> ss.StaffSheet:
    member, venue = staff_for(session, user, staff_id)
    record(session, now, STAFF_REPORT_VIEW, "staff", staff_id, user=user, after={"sheet": True}, request=request)
    session.commit()
    org = session.get(models.Organization, user.organization_id)
    return svc.sheet(session, venue, member, now, org.staff_retention_days if org else 60)


@router.get("/audit", response_model=ss.AuditList, responses=RESPONSES)
def audit(
    user: OwnerUser, session: SessionDep, now: NowDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> ss.AuditList:
    return svc.audit_entries(session, user.organization_id, STAFF_REPORT_VIEW, now, limit)


@router.post("/venues/{venue_id}/till/import", response_model=ss.TillImportResult, responses=RESPONSES)
def import_till(
    venue_id: str, payload: ss.TillImportIn, user: BusinessUser, session: SessionDep, now: NowDep, request: Request
) -> ss.TillImportResult:
    venue = venue_for(session, user, venue_id)
    outcome = svc.import_till(session, venue, payload, now)
    if outcome.saved:
        record(
            session,
            now,
            "business.till.import",
            "venue",
            venue.id,
            user=user,
            after={"new_orders": outcome.new_orders, "rows": outcome.rows},
            request=request,
        )
        session.commit()
    return outcome


@router.get("/venues/{venue_id}/sales", response_model=ss.SalesDay, responses=RESPONSES)
def get_sales(
    venue_id: str, user: BusinessUser, session: SessionDep, now: NowDep, day: Annotated[date | None, Query()] = None
) -> ss.SalesDay:
    venue = venue_for(session, user, venue_id)
    return svc.sales(session, venue, svc.local_day(venue, now, day), now)


@router.get("/venues/{venue_id}/cameras/{device_id}/live", response_model=ss.LiveLink, responses=RESPONSES)
def live_link(
    venue_id: str, device_id: str, user: BusinessUser, session: SessionDep, now: NowDep, real_now: RealNowDep
) -> ss.LiveLink:
    venue = venue_for(session, user, venue_id)
    device = session.get(models.Device, device_id)
    if device is None or device.canteen_id != venue.id:
        raise not_found("Device", device_id)
    return svc.live_link(device, now, real_now)


@devices.get("/devices/{device_id}/staff-templates", response_model=ss.StaffTemplates, responses=AUTH_RESPONSES)
def staff_templates(device: DeviceDep, session: SessionDep, settings: SettingsDep, now: NowDep) -> ss.StaffTemplates:
    if not models.is_venue_id(device.canteen_id):
        raise not_found("Venue", device.canteen_id)
    return svc.templates_for(session, settings, device, now)


@devices.post("/devices/{device_id}/staff", response_model=ss.StaffAccepted, responses=AUTH_RESPONSES)
def post_staff(
    payload: ss.StaffSnapshotIn, device: DeviceDep, session: SessionDep, now: NowDep, real_now: RealNowDep
) -> ss.StaffAccepted:
    if not models.is_venue_id(device.canteen_id):
        raise not_found("Venue", device.canteen_id)
    if payload.captured_at > real_now + MAX_FUTURE_SKEW:
        raise ApiError(422, "validation_error", "captured_at is more than 60 s in the future.")
    stored, queued = svc.accept_staff(session, device, payload, now - real_now, device.kind == "simulator")
    device.last_heartbeat_at = now
    session.commit()
    return ss.StaffAccepted(server_time=now, device_id=device.id, presence=stored, queue=queued)
