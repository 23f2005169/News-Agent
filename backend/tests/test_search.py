"""Tests for the search endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_search_endpoint_returns_supabase_results(monkeypatch):
    from app.routers import search

    class FakeResult:
        data = [{"id": "item-1", "title": "Example result"}]

    class FakeSupabase:
        def rpc(self, name, payload):
            assert name == "match_items"
            assert payload["query_embedding"] == [0.1, 0.2]
            assert payload["match_count"] == 3
            assert payload["exclude_id"] is None
            return self

        def execute(self):
            return FakeResult()

    monkeypatch.setattr(search, "embed_text", lambda text: [0.1, 0.2])
    monkeypatch.setattr(search, "get_supabase_client", lambda: FakeSupabase())

    client = TestClient(app)
    response = client.get("/search/", params={"query": "climate", "limit": 3})

    assert response.status_code == 200
    assert response.json() == {
        "query": "climate",
        "limit": 3,
        "results": [{"id": "item-1", "title": "Example result"}],
    }