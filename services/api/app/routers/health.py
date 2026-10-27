from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app import __version__
from app.core.config import Settings, get_settings
from app.core.db import database_reachable

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    simulation_mode: bool
    version: str
    server_time: datetime


@router.get("/health", response_model=HealthResponse)
def health(
    response: Response,
    db_ok: Annotated[bool, Depends(database_reachable)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="ok" if db_ok else "unavailable",
        simulation_mode=settings.simulation_mode,
        version=__version__,
        server_time=datetime.now(UTC),
    )
