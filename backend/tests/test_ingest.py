"""Ingestion path: single + batch writes into real OpenSearch."""
import pytest

pytestmark = pytest.mark.integration


def _log(**over):
    base = {
        "service": "payment-service",
        "level": "ERROR",
        "message": "payment gateway timeout",
        "timestamp": "2026-01-15T12:00:00Z",
    }
    base.update(over)
    return base


def test_ingest_single_returns_id(client):
    resp = client.post("/logs/ingest", json=_log())
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) == 1
    assert body[0]["id"]  # OpenSearch _id populated
    assert body[0]["service"] == "payment-service"
    assert body[0]["level"] == "ERROR"


def test_ingest_batch_returns_all_ids(client):
    logs = [_log(message=f"err {i}") for i in range(5)]
    resp = client.post("/logs/ingest", json=logs)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
    ids = [row["id"] for row in body]
    assert len(set(ids)) == 5  # all distinct


def test_ingested_log_is_searchable(seed_logs, client):
    seed_logs([_log(message="unique-token-xyz")])
    resp = client.get("/logs/search", params={"q": "unique-token-xyz"})
    assert resp.status_code == 200
    hits = resp.json()
    assert len(hits) == 1
    assert hits[0]["message"] == "unique-token-xyz"


def test_default_timestamp_applied_when_omitted(client):
    payload = {"service": "svc", "level": "INFO", "message": "no ts"}
    resp = client.post("/logs/ingest", json=payload)
    assert resp.status_code == 200
    assert resp.json()[0]["timestamp"]  # server filled default_factory


def test_metadata_roundtrips(seed_logs, client):
    meta = {"region": "us-west-2", "attempt": 3}
    seed_logs([_log(metadata=meta)])
    hits = client.get("/logs/search", params={"service": "payment-service"}).json()
    assert hits[0]["metadata"] == meta


def test_trace_id_optional_and_preserved(seed_logs, client):
    seed_logs([_log(trace_id="abc-123")])
    hits = client.get("/logs/search", params={"service": "payment-service"}).json()
    assert hits[0]["trace_id"] == "abc-123"
