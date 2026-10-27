from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import get_settings
from app.routers import health

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DineMate API",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "If-Match"],
    )
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
