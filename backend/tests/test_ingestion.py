"""Tests for pollers, normalization, and exact dedup on insert.

DB tests run against an in-memory SQLite database (models.py uses
dialect-agnostic types for exactly this) — no Postgres needed for CI/local dev.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ingestion.normalizer import canonicalize_url, normalize_gnews, url_hash


@pytest.fixture()
def db_session(monkeypatch):
    """Point SessionLocal at a fresh in-memory SQLite DB for each test."""
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    from app.db.models import Base

    Base.metadata.create_all(bind=engine)
    # Patch the global session factory used by ingestion/scheduler/dedup and the poller.
    for mod_path in (
        "app.db.postgres",
        "app.ingestion.scheduler",
        "app.processing.dedup",
    ):
        monkeypatch.setattr(f"{mod_path}.SessionLocal", TestingSession, raising=False)
    return TestingSession


RAW_ARTICLE = {
    "title": "OpenAI releases new model",
    "description": "OpenAI announced a new model today.",
    "url": "https://Example.COM/news/article/?utm_source=feed&utm_medium=rss&id=42#comments",
    "publishedAt": "2026-09-15T10:30:00Z",
}


def test_canonicalize_url_strips_tracking_and_case():
    assert canonicalize_url(RAW_ARTICLE["url"]) == "https://example.com/news/article?id=42"


def test_normalize_gnews_maps_schema():
    item = normalize_gnews(RAW_ARTICLE)
    assert item["source_type"] == "news"
    assert item["source_name"] == "gnews"
    assert item["title"] == "OpenAI releases new model"
    assert item["published_at"] == datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)
    assert item["external_id"] == url_hash(RAW_ARTICLE["url"])


def test_poll_run_inserts_and_is_idempotent(db_session, monkeypatch):
    """Poll with a mocked HTTP layer; a second identical poll must insert nothing."""
    from app.ingestion.pollers import news_poller

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"articles": [RAW_ARTICLE, RAW_ARTICLE]}  # dup within page too

    monkeypatch.setattr(news_poller.httpx, "get", lambda *a, **k: FakeResponse())
    monkeypatch.setattr(news_poller, "get_last_poll_timestamp", lambda s: datetime(2026, 9, 1, tzinfo=timezone.utc))

    assert news_poller.run() == 1
    assert news_poller.run() == 0  # idempotent on overlapping poll windows


def test_cursor_roundtrip(db_session):
    from app.ingestion.scheduler import get_last_poll_timestamp, set_last_poll_timestamp

    ts = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    set_last_poll_timestamp("gnews", ts)
    got = get_last_poll_timestamp("gnews")
    assert got.replace(tzinfo=timezone.utc) == ts
