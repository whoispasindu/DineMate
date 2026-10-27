from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import get_settings
from app.core.errors import install_error_handling
from app.routers import canteens, devices, health, schedules, shops, student

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
    install_error_handling(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "If-Match"],
        expose_headers=["X-Request-ID"],
    )
    for router in (health.router, student.router, canteens.router, shops.router, schedules.router, devices.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
