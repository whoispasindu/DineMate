import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.business.service import purge_expired
from app.business.staff_service import purge_staff_data
from app.core import clock
from app.core.config import get_settings
from app.core.db import get_engine
from app.safety.service import check_sources
from app.services.retention import purge_old_data
from app.services.rules import evaluate
from app.testfeeds.storage import purge_orphans

log = logging.getLogger("dinemate.rules")


def run_rules_once() -> None:
    with Session(get_engine()) as session:
        result = evaluate(session, clock.now())
        offline = check_sources(session, clock.now())
        purge_expired(session, clock.now())
        purge_staff_data(session, clock.now())
        session.commit()
    if offline:
        log.info("safety sources changed state: %s", len(offline))
    if result.opened or result.changed or result.resolved:
        log.info("alerts opened=%s changed=%s resolved=%s", result.opened, result.changed, result.resolved)


def run_retention_once() -> None:
    settings = get_settings()
    with Session(get_engine()) as session:
        removed = purge_old_data(session, clock.now(), datetime.now(UTC), settings)
        removed["test_videos"] = purge_orphans(session, settings, time.time())
        session.commit()
    if any(removed.values()):
        log.info("retention removed %s", {name: count for name, count in removed.items() if count})


async def rules_loop(interval_s: float) -> None:
    retention_every = get_settings().retention_interval_s
    next_retention = time.monotonic()
    while True:
        try:
            await asyncio.to_thread(run_rules_once)
            if retention_every > 0 and time.monotonic() >= next_retention:
                next_retention = time.monotonic() + retention_every
                await asyncio.to_thread(run_retention_once)
        except (SQLAlchemyError, OSError) as exc:
            log.warning("rules evaluation skipped: %s", exc.__class__.__name__)
        await asyncio.sleep(interval_s)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    interval = get_settings().rules_interval_s
    task = asyncio.create_task(rules_loop(interval)) if interval > 0 else None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
