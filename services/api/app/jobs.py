import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.business.service import purge_expired
from app.business.staff_service import purge_staff_data
from app.core import clock
from app.core.config import get_settings
from app.core.db import get_engine
from app.safety.service import check_sources
from app.services.rules import evaluate

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


async def rules_loop(interval_s: float) -> None:
    while True:
        try:
            await asyncio.to_thread(run_rules_once)
        except SQLAlchemyError as exc:
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
