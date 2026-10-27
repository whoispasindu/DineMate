import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.db import get_session
from app.main import app
from app.seed import reset, seed
from app.services.timeutil import CAMPUS_TZ

TEST_DATABASE_URL = os.environ.get(
    "DINEMATE_TEST_DATABASE_URL", "postgresql+psycopg://dinemate:dinemate@localhost:5432/dinemate_test"
)
REQUIRE_DB = os.environ.get("DINEMATE_REQUIRE_DB_TESTS") == "1"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

LUNCH_NOW = datetime(2026, 11, 20, 12, 41, 18, tzinfo=CAMPUS_TZ).astimezone(UTC)


def _ensure_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3}
    )
    try:
        with admin.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database})
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as exc:
        if REQUIRE_DB:
            raise
        pytest.skip(f"Postgres not reachable for integration tests: {exc.__class__.__name__}")
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    _ensure_database()
    url = make_url(TEST_DATABASE_URL).render_as_string(hide_password=False)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def seeded(db_engine: Engine) -> Engine:
    with Session(db_engine) as session:
        reset(session)
        seed(session, LUNCH_NOW)
    return db_engine


def client_at(engine: Engine, now: datetime) -> TestClient:
    def session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_now] = lambda: now
    return TestClient(app)


@pytest.fixture
def api(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as client:
        yield client
    app.dependency_overrides.clear()
