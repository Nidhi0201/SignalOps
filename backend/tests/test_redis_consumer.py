"""
Real tests for the async Redis-Streams consumer (Milestone 1).

Covers consumer-group processing, batching, redelivery/claim on worker death,
dead-lettering after the retry cap, and the full ingest -> consumer -> search
pipeline. Runs against real Redis + OpenSearch testcontainers.
"""
import json

import pytest

from app import consumer
from app.redis_client import LOG_DLQ_STREAM, LOG_GROUP, LOG_STREAM

pytestmark = pytest.mark.integration


def _src(**over):
    base = {"service": "s", "level": "ERROR", "message": "m",
            "timestamp": "2026-01-15T12:00:00", "metadata": {}}
    base.update(over)
    return base


def _xadd(r, **over):
    return r.xadd(LOG_STREAM, {"data": json.dumps(_src(**over))})


def _pending(r):
    return r.xpending(LOG_STREAM, LOG_GROUP)["pending"]


def test_ensure_group_is_idempotent(redis_client):
    consumer.ensure_group(redis_client)
    consumer.ensure_group(redis_client)  # BUSYGROUP swallowed
    groups = redis_client.xinfo_groups(LOG_STREAM)
    assert any(g["name"] == LOG_GROUP for g in groups)


def test_process_new_indexes_and_acks(redis_client, opensearch_client):
    consumer.ensure_group(redis_client)
    for i in range(3):
        _xadd(redis_client, message=f"m{i}")
    stats = consumer.process_new(redis_client, opensearch_client, "w1",
                                 batch_size=10, block_ms=200)
    assert stats == {"read": 3, "indexed": 3, "failed": 0}
    opensearch_client.indices.refresh(index="logs")
    assert opensearch_client.count(index="logs")["count"] == 3
    assert _pending(redis_client) == 0  # everything acked


def test_batch_read_in_single_call(redis_client, opensearch_client):
    consumer.ensure_group(redis_client)
    for i in range(25):
        _xadd(redis_client, message=f"m{i}")
    stats = consumer.process_new(redis_client, opensearch_client, "w1",
                                 batch_size=50, block_ms=200)
    assert stats["read"] == 25  # one bulk for the whole batch


def test_doc_id_is_stream_id_so_retries_dont_duplicate(redis_client, opensearch_client):
    consumer.ensure_group(redis_client)
    eid = _xadd(redis_client, message="idem")
    # Index the same entry twice (simulating a redelivery).
    consumer.index_batch(opensearch_client, [(eid, {"data": json.dumps(_src(message="idem"))})])
    consumer.index_batch(opensearch_client, [(eid, {"data": json.dumps(_src(message="idem"))})])
    opensearch_client.indices.refresh(index="logs")
    assert opensearch_client.count(index="logs")["count"] == 1  # overwrote, no dup


def test_redelivery_claim_on_worker_death(redis_client, opensearch_client):
    consumer.ensure_group(redis_client)
    _xadd(redis_client, message="orphan")
    # Worker A reads but dies before acking.
    redis_client.xreadgroup(LOG_GROUP, "workerA", {LOG_STREAM: ">"}, count=10)
    assert _pending(redis_client) == 1
    # Worker B claims the stale entry (min_idle 0) and processes it.
    stats = consumer.reclaim(redis_client, opensearch_client, "workerB",
                             min_idle_ms=0, max_retries=3)
    assert stats["reclaimed"] == 1 and stats["indexed"] == 1
    opensearch_client.indices.refresh(index="logs")
    assert opensearch_client.count(index="logs")["count"] == 1
    assert _pending(redis_client) == 0


def test_dead_letter_after_retry_cap(redis_client, opensearch_client):
    consumer.ensure_group(redis_client)
    _xadd(redis_client, message="poison")
    redis_client.xreadgroup(LOG_GROUP, "workerA", {LOG_STREAM: ">"}, count=10)  # delivery=1

    def always_fail(_os, entries):
        return set(), {eid for eid, _ in entries}

    # Each reclaim increments delivery count; with cap=2 the entry is DLQ'd
    # once times_delivered exceeds 2.
    for _ in range(4):
        consumer.reclaim(redis_client, opensearch_client, "workerB",
                         min_idle_ms=0, max_retries=2, index_fn=always_fail)

    assert redis_client.xlen(LOG_DLQ_STREAM) == 1
    assert _pending(redis_client) == 0  # removed from the main PEL


def test_pipeline_end_to_end(client, redis_client, opensearch_client):
    # Async ingest -> Redis Stream -> consumer -> searchable in OpenSearch.
    resp = client.post("/logs/ingest", json={
        "service": "payment", "level": "ERROR", "message": "pipeline-e2e",
        "timestamp": "2026-01-15T12:00:00Z"})
    assert resp.status_code == 202

    consumer.ensure_group(redis_client)
    consumer.process_new(redis_client, opensearch_client, "w1", batch_size=10, block_ms=200)
    opensearch_client.indices.refresh(index="logs")

    hits = client.get("/logs/search", params={"q": "pipeline-e2e"}).json()
    assert len(hits) == 1
    assert hits[0]["message"] == "pipeline-e2e"
