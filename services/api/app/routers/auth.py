from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import func, select, update

from app import models
from app.core.auth import UserDep
from app.core.config import Settings, get_settings
from app.core.deps import SessionDep
from app.core.device_auth import RealNowDep
from app.core.errors import ApiError
from app.core.security import (
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    create_access_token,
    hash_password,
    hash_refresh_token,
    login_limiter,
    needs_rehash,
    new_refresh_token,
    verify_password,
)
from app.schemas import ErrorResponse
from app.schemas_auth import LoginIn, Me, Session
from app.services.audit import client_ip, record

router = APIRouter(prefix="/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
AUTH_ERRORS: dict[int | str, dict[str, Any]] = {401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}}
DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")
REUSE_GRACE = timedelta(seconds=30)


def me_schema(user: models.User) -> Me:
    return Me(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,  # type: ignore[arg-type]
        canteen_ids=sorted(user.canteen_ids),
        shop_ids=sorted(user.shop_ids),
    )


def _issue(session: SessionDep, user: models.User, response: Response, settings: Settings, now: datetime) -> Session:
    raw = new_refresh_token()
    session.add(
        models.RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            created_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_days),
        )
    )
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 86_400,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    token, expires_in = create_access_token(str(user.id), user.role, settings, now)
    return Session(access_token=token, token_type="bearer", expires_in=expires_in, user=me_schema(user))


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.post("/login", response_model=Session, responses=AUTH_ERRORS)
def login(
    payload: LoginIn, request: Request, response: Response, session: SessionDep, settings: SettingsDep, now: RealNowDep
) -> Session:
    if not login_limiter.allow(client_ip(request) or "unknown", settings.login_attempts_per_minute):
        raise ApiError(429, "rate_limited", "Too many sign-in attempts. Wait a minute and try again.")
    user = session.scalars(
        select(models.User).where(func.lower(models.User.email) == payload.email.strip().lower())
    ).first()
    if user is None or not user.is_active:
        verify_password(payload.password, DUMMY_HASH)
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    if not verify_password(payload.password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = now
    result = _issue(session, user, response, settings, now)
    record(session, now, "auth.login", "user", str(user.id), user=user, request=request)
    session.commit()
    return result


@router.post("/refresh", response_model=Session, responses=AUTH_ERRORS)
def refresh(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    now: RealNowDep,
    dinemate_refresh: Annotated[str | None, Cookie()] = None,
) -> Session:
    if not dinemate_refresh:
        raise ApiError(401, "unauthenticated", "Please sign in.")
    stored = session.scalars(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == hash_refresh_token(dinemate_refresh))
    ).first()
    if stored is None or stored.expires_at <= now:
        _clear_cookie(response)
        raise ApiError(401, "unauthenticated", "Your session has expired. Please sign in again.")
    if stored.revoked_at is not None and now - stored.revoked_at > REUSE_GRACE:
        session.execute(
            update(models.RefreshToken)
            .where(models.RefreshToken.user_id == stored.user_id, models.RefreshToken.expires_at > now)
            .values(revoked_at=func.coalesce(models.RefreshToken.revoked_at, now), expires_at=now)
        )
        session.commit()
        _clear_cookie(response)
        raise ApiError(401, "unauthenticated", "This session was already used. Please sign in again.")
    user = session.get(models.User, stored.user_id)
    if user is None or not user.is_active:
        _clear_cookie(response)
        raise ApiError(401, "unauthenticated", "Please sign in.")
    stored.revoked_at = stored.revoked_at or now
    result = _issue(session, user, response, settings, now)
    session.commit()
    return result


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    session: SessionDep,
    now: RealNowDep,
    dinemate_refresh: Annotated[str | None, Cookie()] = None,
) -> Response:
    response = Response(status_code=204)
    if dinemate_refresh:
        stored = session.scalars(
            select(models.RefreshToken).where(models.RefreshToken.token_hash == hash_refresh_token(dinemate_refresh))
        ).first()
        if stored is not None and stored.expires_at > now:
            stored.revoked_at = stored.revoked_at or now
            stored.expires_at = now
            record(session, now, "auth.logout", "user", str(stored.user_id), request=request)
            session.commit()
    _clear_cookie(response)
    return response


@router.get("/me", response_model=Me, responses={401: {"model": ErrorResponse}})
def me(user: UserDep) -> Me:
    return me_schema(user)
