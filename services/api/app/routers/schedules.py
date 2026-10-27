from fastapi import APIRouter

from app import models, schemas
from app.core.deps import NowDep, SessionDep
from app.core.errors import NOT_FOUND_RESPONSE, not_found
from app.services.views import meal_status_schema

router = APIRouter(tags=["schedules"])


@router.get("/meal-status", response_model=schemas.MealStatus, responses=NOT_FOUND_RESPONSE)
def get_meal_status(session: SessionDep, now: NowDep, canteen_id: str | None = None) -> schemas.MealStatus:
    if canteen_id is not None and session.get(models.Canteen, canteen_id) is None:
        raise not_found("Canteen", canteen_id)
    return meal_status_schema(session, now, canteen_id)
