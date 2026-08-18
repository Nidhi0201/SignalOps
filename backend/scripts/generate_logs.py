"""
Realistic structured-log generator for scale testing.

Bulk-indexes N logs across several services with a configurable error rate and
timestamps spread over a recent window, then reports sustained indexing
throughput. Uses the same "logs" mapping as the app.

Usage (needs OpenSearch reachable):
    OPENSEARCH_PORT=9200 python -m scripts.generate_logs --count 1000000
"""
import argparse
import os
import random
import time
from datetime import datetime, timedelta

from opensearchpy import OpenSearch, helpers

INDEX = "logs"
SERVICES = ["payment", "auth", "checkout", "search", "inventory",
            "notification", "gateway", "recommendation"]
LEVELS_OK = ["INFO", "INFO", "INFO", "DEBUG", "WARN"]  # non-error mix
LEVELS_ERR = ["ERROR", "ERROR", "FATAL"]
REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"]

MESSAGES = {
    "INFO": ["request completed", "user logged in", "cache hit", "job finished",
             "health check ok", "config loaded"],
    "DEBUG": ["entering handler", "query executed", "payload parsed", "retry scheduled"],
    "WARN": ["slow response", "deprecated endpoint used", "retry attempt", "high memory"],
    "ERROR": ["database timeout", "connection refused", "null pointer in handler",
              "payment gateway error", "unhandled exception", "request failed"],
    "FATAL": ["out of memory", "service crashed", "data corruption detected"],
}

MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "service": {"type": "keyword"},
            "level": {"type": "keyword"},
            "message": {"type": "text"},
            "trace_id": {"type": "keyword"},
            "metadata": {"type": "object", "enabled": True},
        }
    }
}


def client() -> OpenSearch:
    return OpenSearch(
        hosts=[{"host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200"))}],
        http_auth=None, use_ssl=False, verify_certs=False, timeout=120,
    )


def gen_docs(count, error_rate, window_days, rng):
    base = datetime.utcnow() - timedelta(days=window_days)
    span = window_days * 24 * 3600
    for _ in range(count):
        is_err = rng.random() < error_rate
        level = rng.choice(LEVELS_ERR if is_err else LEVELS_OK)
        service = rng.choice(SERVICES)
        ts = base + timedelta(seconds=rng.random() * span)
        yield {
            "_index": INDEX,
            "_source": {
                "timestamp": ts.isoformat(),
                "service": service,
                "level": level,
                "message": f"{service}: {rng.choice(MESSAGES[level])}",
                "trace_id": f"{rng.getrandbits(64):016x}",
                "metadata": {"region": rng.choice(REGIONS),
                             "host": f"{service}-{rng.randint(1, 20)}"},
            },
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1_000_000)
    ap.add_argument("--error-rate", type=float, default=0.08)
    ap.add_argument("--window-days", type=int, default=30)
    ap.add_argument("--batch", type=int, default=5000)
    ap.add_argument("--recreate", action="store_true", help="drop the index first")
    args = ap.parse_args()

    c = client()
    if args.recreate and c.indices.exists(index=INDEX):
        c.indices.delete(index=INDEX)
    if not c.indices.exists(index=INDEX):
        # refresh_interval=-1 disables refresh during bulk load for speed;
        # restored afterwards.
        c.indices.create(index=INDEX, body={**MAPPING, "settings": {"refresh_interval": "-1"}})

    rng = random.Random(7)
    start = time.perf_counter()
    indexed = 0
    for ok, _ in helpers.streaming_bulk(
        c, gen_docs(args.count, args.error_rate, args.window_days, rng),
        chunk_size=args.batch, max_retries=3, raise_on_error=False,
    ):
        indexed += 1 if ok else 0
        if indexed % 100_000 == 0 and indexed:
            rate = indexed / (time.perf_counter() - start)
            print(f"  {indexed:,} indexed  ({rate:,.0f} docs/sec)")

    elapsed = time.perf_counter() - start
    c.indices.put_settings(index=INDEX, body={"refresh_interval": "1s"})
    c.indices.refresh(index=INDEX)

    print("\n" + "=" * 52)
    print("INGESTION (bulk load)")
    print("=" * 52)
    print(f"  indexed {indexed:,} docs in {elapsed:,.1f}s")
    print(f"  sustained throughput: {indexed/elapsed:,.0f} docs/sec")
    count = c.count(index=INDEX)["count"]
    print(f"  index now holds {count:,} documents")
    print("=" * 52)


if __name__ == "__main__":
    main()
