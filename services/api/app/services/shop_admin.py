from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from itertools import pairwise
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.core.errors import ApiError
from app.models.base import PERIOD_VALUES
from app.schemas_manage import (
    EditableMenuItem,
    HoursException,
    MenuItemFields,
    MenuItemPatch,
    ShopEditor,
    ShopHoursIn,
    WeeklyHours,
)
from app.services.views import shop_view

DELETE_MARK = "delete"


def invalid(message: str, **details: Any) -> ApiError:
    return ApiError(422, "validation_error", message, details or None)


def item_fields(item: models.MenuItem) -> MenuItemFields:
    return MenuItemFields(
        name=item.name,
        price_lkr=Decimal(item.price_cents) / 100,
        category=item.category,  # type: ignore[arg-type]
        dietary_tags=list(item.dietary_tags),  # type: ignore[arg-type]
        periods=sorted({p.period for p in item.periods}, key=PERIOD_VALUES.index),  # type: ignore[arg-type]
    )


def draft_fields(draft: dict[str, Any]) -> MenuItemFields:
    return MenuItemFields(
        name=draft["name"],
        price_lkr=Decimal(draft["price_cents"]) / 100,
        category=draft.get("category"),
        dietary_tags=draft.get("dietary_tags", []),
        periods=draft["periods"],
    )


def draft_dict(fields: MenuItemFields) -> dict[str, Any]:
    return {
        "name": fields.name,
        "price_cents": int(fields.price_lkr * 100),
        "category": fields.category,
        "dietary_tags": sorted(set(fields.dietary_tags)),
        "periods": sorted(set(fields.periods), key=PERIOD_VALUES.index),
    }


def editable(item: models.MenuItem) -> EditableMenuItem:
    if not item.is_published:
        live, draft, pending = None, item_fields(item), "new"
    elif item.draft and item.draft.get(DELETE_MARK):
        live, draft, pending = item_fields(item), None, "delete"
    elif item.draft:
        live, draft, pending = item_fields(item), draft_fields(item.draft), "edit"
    else:
        live, draft, pending = item_fields(item), None, "none"
    return EditableMenuItem(
        id=str(item.id),
        live=live,
        draft=draft,
        pending=pending,  # type: ignore[arg-type]
        is_available=item.is_available,
        availability_updated_at=item.availability_updated_at,
    )


def shop_items(session: Session, shop_id: str) -> list[models.MenuItem]:
    stmt = (
        select(models.MenuItem)
        .options(selectinload(models.MenuItem.periods))
        .where(models.MenuItem.shop_id == shop_id)
        .order_by(models.MenuItem.sort_order, models.MenuItem.name)
    )
    return list(session.scalars(stmt))


def pending_count(items: list[models.MenuItem]) -> int:
    return sum(1 for item in items if not item.is_published or item.draft)


def canteen_name(session: Session, canteen_id: str) -> str:
    canteen = session.get(models.Canteen, canteen_id)
    return canteen.name if canteen else canteen_id


def shop_editor(session: Session, shop: models.Shop, now: datetime) -> ShopEditor:
    items = shop_items(session, shop.id)
    return ShopEditor(
        server_time=now,
        shop=shop_view(shop, canteen_name(session, shop.canteen_id), now),
        weekly=[WeeklyHours(weekday=h.weekday, opens=h.opens, closes=h.closes) for h in shop.hours],
        exceptions=[
            HoursException(date=e.date, is_closed=e.is_closed, opens=e.opens, closes=e.closes, reason=e.reason)
            for e in sorted(shop.exceptions, key=lambda e: e.date)
        ],
        temporarily_closed_until=shop.temporarily_closed_until,
        closure_reason=shop.closure_reason,
        items=[editable(item) for item in items],
        pending_changes=pending_count(items),
    )


def hours_snapshot(shop: models.Shop) -> dict[str, Any]:
    return {
        "weekly": [[h.weekday, h.opens, h.closes] for h in shop.hours],
        "exceptions": [[e.date, e.is_closed, e.opens, e.closes, e.reason] for e in shop.exceptions],
    }


def validate_hours(payload: ShopHoursIn) -> None:
    by_day: dict[int, list[WeeklyHours]] = defaultdict(list)
    for slot in payload.weekly:
        if slot.opens >= slot.closes:
            raise invalid("Opening time must be before closing time.", weekday=slot.weekday)
        by_day[slot.weekday].append(slot)
    for weekday, slots in by_day.items():
        ordered = sorted(slots, key=lambda s: s.opens)
        for earlier, later in pairwise(ordered):
            if later.opens < earlier.closes:
                raise invalid("Opening intervals on the same day can't overlap.", weekday=weekday)
    seen: set[str] = set()
    for exception in payload.exceptions:
        key = exception.date.isoformat()
        if key in seen:
            raise invalid("Each date can have only one exception.", date=key)
        seen.add(key)
        if not exception.is_closed and (
            exception.opens is None or exception.closes is None or exception.opens >= exception.closes
        ):
            raise invalid("Special hours need an opening time before the closing time.", date=key)


def replace_hours(session: Session, shop: models.Shop, payload: ShopHoursIn) -> None:
    session.execute(delete(models.ShopHours).where(models.ShopHours.shop_id == shop.id))
    session.execute(delete(models.ShopHourException).where(models.ShopHourException.shop_id == shop.id))
    for slot in payload.weekly:
        session.add(models.ShopHours(shop_id=shop.id, weekday=slot.weekday, opens=slot.opens, closes=slot.closes))
    for e in payload.exceptions:
        session.add(
            models.ShopHourException(
                shop_id=shop.id,
                date=e.date,
                is_closed=e.is_closed,
                opens=None if e.is_closed else e.opens,
                closes=None if e.is_closed else e.closes,
                reason=e.reason or None,
            )
        )
    session.flush()
    session.expire(shop, ["hours", "exceptions"])


def set_periods(item: models.MenuItem, periods: list[str]) -> None:
    wanted = set(periods)
    item.periods = [p for p in item.periods if p.period in wanted] + [
        models.MenuItemPeriod(period=p) for p in sorted(wanted - {p.period for p in item.periods})
    ]


def apply_fields(item: models.MenuItem, data: dict[str, Any]) -> None:
    item.name = data["name"]
    item.price_cents = data["price_cents"]
    item.category = data["category"]
    item.dietary_tags = data["dietary_tags"]
    set_periods(item, data["periods"])


def edit_item(item: models.MenuItem, patch: MenuItemPatch) -> None:
    base = item.draft if item.is_published and item.draft and not item.draft.get(DELETE_MARK) else None
    current = draft_fields(base) if base else item_fields(item)
    merged = MenuItemFields.model_validate({**current.model_dump(), **patch.model_dump(exclude_unset=True)})
    data = draft_dict(merged)
    if not item.is_published:
        apply_fields(item, data)
    elif data == draft_dict(item_fields(item)):
        item.draft = None
    else:
        item.draft = data


def publish(session: Session, items: list[models.MenuItem]) -> dict[str, int]:
    summary = {"added": 0, "changed": 0, "removed": 0}
    for item in items:
        if not item.is_published:
            item.is_published = True
            summary["added"] += 1
        elif item.draft and item.draft.get(DELETE_MARK):
            session.delete(item)
            summary["removed"] += 1
        elif item.draft:
            apply_fields(item, item.draft)
            item.draft = None
            summary["changed"] += 1
    return summary


def discard(session: Session, items: list[models.MenuItem]) -> int:
    dropped = 0
    for item in items:
        if not item.is_published:
            session.delete(item)
            dropped += 1
        elif item.draft:
            item.draft = None
            dropped += 1
    return dropped
