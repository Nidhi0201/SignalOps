"""Ingestion: async path (Redis Stream) and the retained sync path."""
import pytest

from app.redis_client import LOG_STREAM

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


# --- async path --------------------------------------------------------------
def test_async_ingest_returns_202_and_stream_ids(client):
    resp = client.post("/logs/ingest", json=_log())
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] == 1
    assert len(body["stream_ids"]) == 1


def test_async_ingest_batch(client):
    resp = client.post("/logs/ingest", json=[_log(message=f"e{i}") for i in range(5)])
    assert resp.status_code == 202
    assert resp.json()["accepted"] == 5


def test_async_ingest_writes_to_redis_stream(client, redis_client):
    client.post("/logs/ingest", json=[_log(), _log()])
    assert redis_client.xlen(LOG_STREAM) == 2


def test_async_ingest_does_not_index_directly(client, opensearch_client):
    # Async returns before indexing; nothing is searchable until the consumer runs.
    client.post("/logs/ingest", json=_log(message="not-yet-indexed"))
    opensearch_client.indices.refresh(index="logs")
    hits = client.get("/logs/search", params={"q": "not-yet-indexed"}).json()
    assert hits == []


# --- sync path (retained for benchmarking) -----------------------------------
def test_sync_ingest_returns_indexed_docs(client):
    resp = client.post("/logs/ingest/sync", json=_log())
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1 and body[0]["id"]


def test_sync_ingest_is_searchable(seed_logs, client):
    seed_logs([_log(message="unique-token-xyz")])  # seed_logs uses the sync endpoint
    hits = client.get("/logs/search", params={"q": "unique-token-xyz"}).json()
    assert len(hits) == 1


def test_sync_default_timestamp_applied(client):
    resp = client.post("/logs/ingest/sync", json={"service": "s", "level": "INFO", "message": "x"})
    assert resp.status_code == 200
    assert resp.json()[0]["timestamp"]


def test_sync_metadata_roundtrips(seed_logs, client):
    meta = {"region": "us-west-2", "attempt": 3}
    seed_logs([_log(metadata=meta)])
    hits = client.get("/logs/search", params={"service": "payment-service"}).json()
    assert hits[0]["metadata"] == meta
