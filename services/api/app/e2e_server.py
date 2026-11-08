import os
from pathlib import Path

E2E_DATABASE_URL = "postgresql+psycopg://dinemate:dinemate@localhost:5432/dinemate_e2e"
E2E_DEMO_CLOCK = "2026-11-20T12:40:30+05:30"
E2E_PORT = 8001
E2E_ORIGINS = '["http://localhost:5183","http://localhost:5184","http://localhost:5185","http://localhost:4183"]'


def configure() -> None:
    os.environ.setdefault("DINEMATE_DATABASE_URL", E2E_DATABASE_URL)
    os.environ.setdefault("DINEMATE_DEMO_CLOCK_START", E2E_DEMO_CLOCK)
    os.environ.setdefault("DINEMATE_CORS_ORIGINS", E2E_ORIGINS)
    os.environ.setdefault("DINEMATE_DEMO_PASSWORD", "e2e-demo-password")
    os.environ.setdefault("DINEMATE_RULES_INTERVAL_S", "2")
    os.environ.setdefault("DINEMATE_LOGIN_ATTEMPTS_PER_MINUTE", "60")


def prepare() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, make_url, text
    from sqlalchemy.orm import Session

    from app.core import clock
    from app.core.config import get_settings
    from app.seed import reset, seed

    settings = get_settings()
    url = make_url(settings.database_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}):
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        reset(session)
        if settings.demo_clock_start is not None:
            clock.reset_demo_clock(session, settings.demo_clock_start)
        seed(session, clock.now(settings), settings.demo_password)
        history_days = int(os.environ.get("DINEMATE_E2E_HISTORY_DAYS", "0"))
        if history_days > 0:
            from app.seed_history import generate

            generate(session, clock.now(settings), history_days)
    engine.dispose()


def main() -> int:
    configure()
    prepare()
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=E2E_PORT, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
