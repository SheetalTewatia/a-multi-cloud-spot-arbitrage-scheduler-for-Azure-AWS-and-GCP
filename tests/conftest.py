"""Shared test fixtures."""

import json
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from tide.catalog import Catalog, load_catalog
from tide.db import engine
from tide.models import Price

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent


def load_fixture(name: str):
    """Recorded real API responses live in tests/fixtures/."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def catalog() -> Catalog:
    return load_catalog(REPO_ROOT / "catalog.yaml")


@pytest.fixture
def db_session():
    """A session that starts with an empty prices table and rolls everything back afterwards,
    so tests neither see nor destroy real collected data (needs Postgres + migrations)."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    session.execute(delete(Price))
    yield session
    session.close()
    transaction.rollback()
    connection.close()
