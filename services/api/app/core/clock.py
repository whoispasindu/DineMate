from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_engine
from app.models import AppState

DEMO_CLOCK_KEY = "demo_clock"

_anchor: tuple[datetime, datetime] | None = None


def _load_anchor(session: Session, demo_start: datetime) -> tuple[datetime, datetime]:
    stmt = insert(AppState).values(
        key=DEMO_CLOCK_KEY,
        value={"demo_start": demo_start.isoformat(), "real_anchor": datetime.now(UTC).isoformat()},
    )
    session.execute(stmt.on_conflict_do_nothing(index_elements=[AppState.key]))
    session.commit()
    value = session.scalars(select(AppState.value).where(AppState.key == DEMO_CLOCK_KEY)).one()
    stored_start = datetime.fromisoformat(value["demo_start"])
    if stored_start != demo_start:
        return reset_demo_clock(session, demo_start)
    return stored_start, datetime.fromisoformat(value["real_anchor"])


def reset_demo_clock(session: Session, demo_start: datetime) -> tuple[datetime, datetime]:
    global _anchor
    real_anchor = datetime.now(UTC)
    value = {"demo_start": demo_start.isoformat(), "real_anchor": real_anchor.isoformat()}
    stmt = insert(AppState).values(key=DEMO_CLOCK_KEY, value=value)
    session.execute(stmt.on_conflict_do_update(index_elements=[AppState.key], set_={"value": value}))
    session.commit()
    _anchor = (demo_start, real_anchor)
    return _anchor


def now(settings: Settings | None = None) -> datetime:
    global _anchor
    settings = settings or get_settings()
    real = datetime.now(UTC)
    if settings.demo_clock_start is None:
        return real
    if _anchor is None or _anchor[0] != settings.demo_clock_start:
        with Session(get_engine()) as session:
            _anchor = _load_anchor(session, settings.demo_clock_start)
    demo_start, real_anchor = _anchor
    return (demo_start + (real - real_anchor)).astimezone(UTC)


def get_now(settings: Annotated[Settings, Depends(get_settings)]) -> datetime:
    return now(settings)
