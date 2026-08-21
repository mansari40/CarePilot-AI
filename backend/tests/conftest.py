"""Test fixtures.

Creates a dedicated `agentcare_test` PostgreSQL database, applies the real Alembic
migrations to it, and truncates all tables before every test so each test starts clean.
"""

import os

from sqlalchemy import create_engine, text

BASE_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://agentcare:agentcare_dev_password@db:5432/agentcare"
)
TEST_DB = "agentcare_test"
MAINTENANCE_URL = BASE_DB_URL.rsplit("/", 1)[0] + "/postgres"
TEST_URL = BASE_DB_URL.rsplit("/", 1)[0] + "/" + TEST_DB

_admin_engine = create_engine(MAINTENANCE_URL, isolation_level="AUTOCOMMIT")
with _admin_engine.connect() as conn:
    exists = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB}
    ).scalar()
    if not exists:
        conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
_admin_engine.dispose()

os.environ["DATABASE_URL"] = TEST_URL

import pytest  # noqa: E402
import alembic.command  # noqa: E402
import alembic.config  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402

_alembic_cfg = alembic.config.Config("alembic.ini")
_alembic_cfg.set_main_option("sqlalchemy.url", TEST_URL)
alembic.command.upgrade(_alembic_cfg, "head")


@pytest.fixture(scope="session")
def db_engine():
    return engine


@pytest.fixture
def db(db_engine):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_tables(db):
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    db.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    db.commit()
    yield