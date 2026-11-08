import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header

from app import models
from app.core.config import Settings, get_settings
from app.core.deps import SessionDep
from app.core.errors import ApiError
from app.core.security import decode_access_token

ADMIN = "campus_admin"
CANTEEN_MANAGER = "canteen_manager"
SHOP_MANAGER = "shop_manager"
SAFETY_OFFICER = "safety_officer"
OWNER = "owner"
VENUE_MANAGER = "venue_manager"


def _unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated", "Please sign in.")


def current_user(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> models.User:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme != "Bearer" or not token:
        raise _unauthenticated()
    claims = decode_access_token(token.strip(), settings)
    if claims is None:
        raise _unauthenticated()
    try:
        user = session.get(models.User, uuid.UUID(str(claims["sub"])))
    except ValueError:
        user = None
    if user is None or not user.is_active:
        raise _unauthenticated()
    return user


UserDep = Annotated[models.User, Depends(current_user)]


def require_roles(*roles: str) -> Callable[[models.User], models.User]:
    def check(user: UserDep) -> models.User:
        if user.role not in roles:
            raise ApiError(403, "forbidden", "Your role can't do this.", {"role": user.role})
        return user

    return check


def can_manage_canteen(user: models.User, canteen_id: str) -> bool:
    if models.is_venue_id(canteen_id):
        return False
    return user.role == ADMIN or (user.role == CANTEEN_MANAGER and canteen_id in user.canteen_ids)


def can_manage_shop(user: models.User, shop: models.Shop) -> bool:
    if user.role == ADMIN:
        return True
    if user.role == CANTEEN_MANAGER:
        return shop.canteen_id in user.canteen_ids
    return user.role == SHOP_MANAGER and shop.id in user.shop_ids


def forbidden_scope(message: str, **details: str) -> ApiError:
    return ApiError(403, "forbidden_scope", message, dict(details))


StaffUser = Annotated[models.User, Depends(require_roles(ADMIN, CANTEEN_MANAGER))]
ShopStaffUser = Annotated[models.User, Depends(require_roles(ADMIN, CANTEEN_MANAGER, SHOP_MANAGER))]
AdminUser = Annotated[models.User, Depends(require_roles(ADMIN))]
