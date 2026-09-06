from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from legal_rag.db.base import Base
from legal_rag.db.models import (  # noqa: F401  (registers models on Base)
    Citation,
    Judgment,
    Paragraph,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """An isolated in-memory SQLite session per test, schema created from the ORM models.

    SQLite stands in for Postgres here: it exercises the same SQLAlchemy
    model layer without requiring a running database for the test suite.
    Migrations (Alembic) are what actually creates the Postgres schema.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
