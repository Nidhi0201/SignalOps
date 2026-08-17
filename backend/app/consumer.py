"""
Async ingestion consumer.

Reads the Redis Stream via a consumer group, bulk-indexes batches into
OpenSearch, and acknowledges only after a successful index (at-least-once).
Documents use the Redis entry ID as the OpenSearch _id, so redeliveries
overwrite rather than duplicate (effectively exactly-once in the index).

Recovery: `reclaim` XAUTOCLAIMs entries left pending by dead/slow workers and
routes entries that exhaust `max_retries` to the dead-letter stream.

Run a worker:  python -m app.consumer
"""
import json
import os
import signal
import time

from opensearchpy import OpenSearch, helpers

from app.redis_client import (
    LOG_DLQ_STREAM,
    LOG_GROUP,
    LOG_STREAM,
    get_redis,
)

BATCH_SIZE = int(os.getenv("CONSUMER_BATCH_SIZE", "500"))
FLUSH_MS = int(os.getenv("CONSUMER_FLUSH_MS", "1000"))  # XREADGROUP BLOCK
MAX_RETRIES = int(os.getenv("CONSUMER_MAX_RETRIES", "3"))
CLAIM_IDLE_MS = int(os.getenv("CONSUMER_CLAIM_IDLE_MS", "30000"))
RECLAIM_EVERY_S = int(os.getenv("CONSUMER_RECLAIM_EVERY_S", "15"))
INDEX = os.getenv("LOG_INDEX", "logs")

_stop = False


def _os_client() -> OpenSearch:
    return OpenSearch(
        hosts=[{"host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200"))}],
        http_auth=None, use_ssl=False, verify_certs=False, timeout=30,
    )


def ensure_group(r, stream=LOG_STREAM, group=LOG_GROUP) -> None:
    """Create the consumer group (and stream) if it does not exist."""
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise


def index_batch(os_client, entries, index=INDEX):
    """Bulk-index entries (id, fields) using the entry id as _id.

    Returns (ok_ids, failed_ids). A whole-batch exception (e.g. OpenSearch
    unreachable) marks every id failed so nothing gets acked.
    """
    if not entries:
        return set(), set()
    actions, ids = [], set()
    for eid, fields in entries:
        ids.add(eid)
        try:
            source = json.loads(fields["data"])
        except (KeyError, json.JSONDecodeError):
            source = {"_raw": fields.get("data")}
        actions.append({"_index": index, "_id": eid, "_source": source})

    try:
        _ok, errors = helpers.bulk(os_client, actions, raise_on_error=False)
    except Exception:
        return set(), ids

    failed = set()
    for err in errors or []:
        for _op, info in err.items():
            if info.get("_id"):
                failed.add(info["_id"])
    return ids - failed, failed


def process_new(r, os_client, consumer, batch_size=BATCH_SIZE, block_ms=FLUSH_MS,
                stream=LOG_STREAM, group=LOG_GROUP, index_fn=index_batch):
    """Read one batch of NEW entries, index, and ack the successes."""
    resp = r.xreadgroup(group, consumer, {stream: ">"}, count=batch_size, block=block_ms)
    entries = resp[0][1] if resp else []
    if not entries:
        return {"read": 0, "indexed": 0, "failed": 0}
    ok, failed = index_fn(os_client, entries)
    if ok:
        r.xack(stream, group, *ok)
    return {"read": len(entries), "indexed": len(ok), "failed": len(failed)}


def reclaim(r, os_client, consumer, min_idle_ms=CLAIM_IDLE_MS, max_retries=MAX_RETRIES,
            batch_size=BATCH_SIZE, stream=LOG_STREAM, group=LOG_GROUP,
            dlq=LOG_DLQ_STREAM, index_fn=index_batch):
    """Claim stale pending entries; DLQ the ones that exhausted retries, index the rest."""
    res = r.xautoclaim(stream, group, consumer, min_idle_ms, start_id="0-0", count=batch_size)
    claimed = [(eid, f) for eid, f in (res[1] if len(res) >= 2 else []) if f is not None]
    if not claimed:
        return {"reclaimed": 0, "indexed": 0, "dlq": 0}

    delivered = {p["message_id"]: p["times_delivered"]
                 for p in r.xpending_range(stream, group, min="-", max="+", count=1000)}
    exhausted = [(eid, f) for eid, f in claimed if delivered.get(eid, 1) > max_retries]
    retriable = [(eid, f) for eid, f in claimed if delivered.get(eid, 1) <= max_retries]

    for eid, fields in exhausted:
        r.xadd(dlq, {"data": fields.get("data", ""), "orig_id": eid,
                     "reason": "max_retries_exceeded"})
        r.xack(stream, group, eid)

    ok, _failed = index_fn(os_client, retriable) if retriable else (set(), set())
    if ok:
        r.xack(stream, group, *ok)
    return {"reclaimed": len(claimed), "indexed": len(ok), "dlq": len(exhausted)}


def _install_signal_handlers() -> None:
    def _handle(_signum, _frame):
        global _stop
        _stop = True
        print("🛑 shutdown signal received; draining current batch...")

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)


def run(consumer: str | None = None) -> None:
    """Main worker loop. Each iteration fully indexes+acks its batch before
    checking the stop flag, so a SIGTERM drains in-flight work rather than
    dropping it."""
    r = get_redis()
    os_client = _os_client()
    ensure_group(r)
    consumer = consumer or f"worker-{os.getpid()}"
    _install_signal_handlers()
    print(f"👷 consumer '{consumer}' started (batch={BATCH_SIZE}, flush={FLUSH_MS}ms)")

    last_reclaim = 0.0
    while not _stop:
        process_new(r, os_client, consumer)
        if time.time() - last_reclaim > RECLAIM_EVERY_S:
            reclaim(r, os_client, consumer)
            last_reclaim = time.time()
    print("✅ consumer drained and stopped")


if __name__ == "__main__":
    run()
