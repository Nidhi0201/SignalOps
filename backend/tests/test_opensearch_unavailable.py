"""
When OpenSearch is unreachable, get_opensearch() must surface a clean 503
rather than leaking a raw connection error. We exercise the REAL dependency
(no override) with OpenSearch monkeypatched to fail on connect.
"""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class _DeadOpenSearch:
    def __init__(self, *args, **kwargs):
        pass

    def info(self):
        raise ConnectionError("simulated: OpenSearch down")


@pytest.fixture
def client_no_opensearch(monkeypatch):
    from app.main import app, get_opensearch

    monkeypatch.setattr("app.main.OpenSearch", _DeadOpenSearch)
    # Ensure the real dependency runs (drop any override a prior fixture set).
    app.dependency_overrides.pop(get_opensearch, None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ingest_returns_503_when_opensearch_down(client_no_opensearch):
    resp = client_no_opensearch.post(
        "/logs/ingest", json={"service": "s", "level": "INFO", "message": "x"}
    )
    assert resp.status_code == 503
    assert "OpenSearch" in resp.json()["detail"]


def test_search_returns_503_when_opensearch_down(client_no_opensearch):
    resp = client_no_opensearch.get("/logs/search", params={"service": "s"})
    assert resp.status_code == 503


def test_health_still_ok_when_opensearch_down(client_no_opensearch):
    # /health has no OpenSearch dependency -> must stay green.
    resp = client_no_opensearch.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
