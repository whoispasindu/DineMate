from typing import get_args

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.core.deps import NowDep, SessionDep
from app.core.errors import NOT_FOUND_RESPONSE, not_found

router = APIRouter(tags=["shops"])

MENU_TAGS = set(get_args(schemas.MenuTag))
PERIODS = get_args(schemas.MealPeriod)


def _tags(item: models.MenuItem) -> list[schemas.MenuTag]:
    raw = ([item.category] if item.category else []) + list(item.dietary_tags)
    return [t for t in dict.fromkeys(raw) if t in MENU_TAGS]  # type: ignore[misc]


@router.get("/shops/{shop_id}/menu", response_model=schemas.Menu, responses=NOT_FOUND_RESPONSE)
def get_menu(shop_id: str, session: SessionDep, now: NowDep, period: schemas.MealPeriod | None = None) -> schemas.Menu:
    shop = session.get(models.Shop, shop_id)
    if shop is None:
        raise not_found("Shop", shop_id)
    stmt = (
        select(models.MenuItem)
        .options(selectinload(models.MenuItem.periods))
        .where(models.MenuItem.shop_id == shop_id, models.MenuItem.is_published)
        .order_by(models.MenuItem.sort_order, models.MenuItem.name)
    )
    items = []
    for item in session.scalars(stmt):
        periods = sorted({p.period for p in item.periods}, key=PERIODS.index)
        if period is not None and period not in periods:
            continue
        items.append(
            schemas.MenuItem(
                id=str(item.id),
                name=item.name,
                price_lkr=item.price_cents / 100,
                tags=_tags(item),
                periods=periods,  # type: ignore[arg-type]
                is_available=item.is_available,
            )
        )
    return schemas.Menu(
        server_time=now, shop_id=shop_id, is_sample=shop.is_sample, items=items, menu_updated_at=shop.menu_updated_at
    )
