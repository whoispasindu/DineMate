import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app import models
from app.core.auth import ShopStaffUser, can_manage_shop, forbidden_scope
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import RealNowDep
from app.core.errors import not_found
from app.schemas import ErrorResponse
from app.schemas_manage import (
    AvailabilityIn,
    AvailabilityResult,
    ClosureIn,
    ManagedShop,
    ManagedShopList,
    MenuItemFields,
    MenuItemPatch,
    ShopEditor,
    ShopHoursIn,
)
from app.services.audit import record
from app.services.shop_admin import (
    DELETE_MARK,
    discard,
    draft_dict,
    edit_item,
    editable,
    hours_snapshot,
    invalid,
    pending_count,
    publish,
    replace_hours,
    set_periods,
    shop_editor,
    shop_items,
    validate_hours,
)
from app.services.views import load_shops, shop_view

router = APIRouter(tags=["shop management"])

MAX_CLOSURE = timedelta(days=30)
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


def managed_shop(session: SessionDep, user: models.User, shop_id: str) -> models.Shop:
    shop = session.get(models.Shop, shop_id)
    if shop is None:
        raise not_found("Shop", shop_id)
    if not can_manage_shop(user, shop):
        raise forbidden_scope("You can only edit shops you manage.", shop_id=shop_id)
    return shop


def managed_item(session: SessionDep, user: models.User, item_id: str) -> tuple[models.MenuItem, models.Shop]:
    try:
        key = uuid.UUID(item_id)
    except ValueError as exc:
        raise not_found("Menu item", item_id) from exc
    item = session.get(models.MenuItem, key)
    if item is None:
        raise not_found("Menu item", item_id)
    return item, managed_shop(session, user, item.shop_id)


@router.get("/manage/shops", response_model=ManagedShopList, responses=RESPONSES)
def list_managed_shops(user: ShopStaffUser, session: SessionDep, now: NowDep) -> ManagedShopList:
    names = {cid: name for cid, name in session.execute(select(models.Canteen.id, models.Canteen.name))}
    shops = [s for s in load_shops(session) if can_manage_shop(user, s)]
    return ManagedShopList(
        server_time=now,
        items=[
            ManagedShop(
                shop=shop_view(s, names.get(s.canteen_id, s.canteen_id), now),
                pending_changes=pending_count(shop_items(session, s.id)),
            )
            for s in shops
        ],
    )


@router.get("/manage/shops/{shop_id}", response_model=ShopEditor, responses=RESPONSES)
def get_shop_editor(shop_id: str, user: ShopStaffUser, session: SessionDep, now: NowDep) -> ShopEditor:
    return shop_editor(session, managed_shop(session, user, shop_id), now)


@router.put("/shops/{shop_id}/hours", response_model=ShopEditor, responses=RESPONSES)
def put_shop_hours(
    shop_id: str,
    payload: ShopHoursIn,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ShopEditor:
    shop = managed_shop(session, user, shop_id)
    validate_hours(payload)
    before = hours_snapshot(shop)
    replace_hours(session, shop, payload)
    record(
        session,
        real_now,
        "shop.hours",
        "shop",
        shop_id,
        user=user,
        before=before,
        after=hours_snapshot(shop),
        request=request,
    )
    session.commit()
    return shop_editor(session, shop, now)


@router.put("/shops/{shop_id}/closure", response_model=ShopEditor, responses=RESPONSES)
def put_shop_closure(
    shop_id: str,
    payload: ClosureIn,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ShopEditor:
    shop = managed_shop(session, user, shop_id)
    if payload.until is not None and payload.until.tzinfo is None:
        raise invalid("Closure end time needs a time zone.")
    if payload.until is not None and not now < payload.until <= now + MAX_CLOSURE:
        raise invalid("A temporary closure must end in the future and within 30 days.")
    before = {"until": shop.temporarily_closed_until, "reason": shop.closure_reason}
    shop.temporarily_closed_until = payload.until
    shop.closure_reason = (payload.reason or None) if payload.until else None
    record(
        session,
        real_now,
        "shop.closure",
        "shop",
        shop_id,
        user=user,
        before=before,
        after={"until": shop.temporarily_closed_until, "reason": shop.closure_reason},
        request=request,
    )
    session.commit()
    return shop_editor(session, shop, now)


@router.post("/shops/{shop_id}/menu-items", status_code=201, response_model=ShopEditor, responses=RESPONSES)
def create_menu_item(
    shop_id: str,
    payload: MenuItemFields,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ShopEditor:
    shop = managed_shop(session, user, shop_id)
    data = draft_dict(payload)
    last = session.scalar(select(func.max(models.MenuItem.sort_order)).where(models.MenuItem.shop_id == shop_id))
    item = models.MenuItem(
        shop_id=shop_id,
        name=data["name"],
        price_cents=data["price_cents"],
        category=data["category"],
        dietary_tags=data["dietary_tags"],
        sort_order=(last or 0) + 1,
        is_available=True,
        availability_updated_at=now,
        is_published=False,
        periods=[],
    )
    set_periods(item, data["periods"])
    session.add(item)
    session.flush()
    record(
        session, real_now, "menu_item.draft_create", "menu_item", str(item.id), user=user, after=data, request=request
    )
    session.commit()
    return shop_editor(session, shop, now)


@router.patch("/menu-items/{item_id}", response_model=ShopEditor, responses=RESPONSES)
def patch_menu_item(
    item_id: str,
    payload: MenuItemPatch,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ShopEditor:
    item, shop = managed_item(session, user, item_id)
    before = editable(item).model_dump(mode="json")
    edit_item(item, payload)
    record(
        session,
        real_now,
        "menu_item.draft_edit",
        "menu_item",
        item_id,
        user=user,
        before=before,
        after=payload.model_dump(mode="json", exclude_unset=True),
        request=request,
    )
    session.commit()
    return shop_editor(session, shop, now)


@router.delete("/menu-items/{item_id}", response_model=ShopEditor, responses=RESPONSES)
def delete_menu_item(
    item_id: str,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ShopEditor:
    item, shop = managed_item(session, user, item_id)
    before = editable(item).model_dump(mode="json")
    if item.is_published:
        item.draft = {DELETE_MARK: True}
    else:
        session.delete(item)
    record(session, real_now, "menu_item.draft_delete", "menu_item", item_id, user=user, before=before, request=request)
    session.commit()
    return shop_editor(session, shop, now)


@router.patch("/menu-items/{item_id}/availability", response_model=AvailabilityResult, responses=RESPONSES)
def set_availability(
    item_id: str,
    payload: AvailabilityIn,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> AvailabilityResult:
    item, _ = managed_item(session, user, item_id)
    if item.is_available != payload.is_available:
        before = {"is_available": item.is_available}
        item.is_available = payload.is_available
        item.availability_updated_at = now
        record(
            session,
            real_now,
            "menu_item.availability",
            "menu_item",
            item_id,
            user=user,
            before=before,
            after={"is_available": payload.is_available},
            request=request,
        )
        session.commit()
    return AvailabilityResult(server_time=now, item=editable(item))


@router.post("/shops/{shop_id}/menu/publish", response_model=ShopEditor, responses=RESPONSES)
def publish_menu(
    shop_id: str,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ShopEditor:
    shop = managed_shop(session, user, shop_id)
    summary = publish(session, shop_items(session, shop_id))
    if any(summary.values()):
        shop.menu_updated_at = now
        record(session, real_now, "menu.publish", "shop", shop_id, user=user, after=summary, request=request)
        session.commit()
    return shop_editor(session, shop, now)


@router.post("/shops/{shop_id}/menu/discard", response_model=ShopEditor, responses=RESPONSES)
def discard_menu_draft(
    shop_id: str,
    user: ShopStaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ShopEditor:
    shop = managed_shop(session, user, shop_id)
    dropped = discard(session, shop_items(session, shop_id))
    if dropped:
        record(
            session, real_now, "menu.discard", "shop", shop_id, user=user, after={"dropped": dropped}, request=request
        )
        session.commit()
    return shop_editor(session, shop, now)
