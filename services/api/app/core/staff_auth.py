import hmac
from typing import Annotated

from fastapi import Depends, Header

from app.core.config import Settings, get_settings
from app.core.errors import ApiError

STAFF_NAME = "Campus administrator"


def staff_user(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme != "Bearer" or not hmac.compare_digest(token.strip(), settings.staff_token):
        raise ApiError(401, "unauthenticated", "Staff sign-in is required.")
    return STAFF_NAME


StaffDep = Annotated[str, Depends(staff_user)]
