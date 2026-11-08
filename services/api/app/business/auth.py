from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app import models
from app.core.auth import OWNER, VENUE_MANAGER, forbidden_scope, require_roles
from app.core.errors import not_found

BusinessUser = Annotated[models.User, Depends(require_roles(OWNER, VENUE_MANAGER))]
OwnerUser = Annotated[models.User, Depends(require_roles(OWNER))]


def venue_for(session: Session, user: models.User, venue_id: str) -> models.Canteen:
    venue = session.get(models.Canteen, venue_id)
    if venue is None or venue.kind != models.VENUE or venue.organization_id != user.organization_id:
        raise not_found("Venue", venue_id)
    if user.role == VENUE_MANAGER and venue_id not in user.canteen_ids:
        raise forbidden_scope("You don't manage this venue.", venue_id=venue_id)
    return venue


def visible_venues(user: models.User, venues: list[models.Canteen]) -> list[models.Canteen]:
    if user.role == OWNER:
        return venues
    return [v for v in venues if v.id in user.canteen_ids]
