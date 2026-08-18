"""
Search latency benchmark at scale.

Measures p50/p95 for free-text and filtered queries against the current "logs"
index, comparing two query shapes:

  baseline   - every clause (term / range / match) in bool.must  (matches the
               app's original search_logs)
  optimized  - term/range clauses moved to bool.filter (cacheable, unscored),
               only the free-text match stays scored, and track_total_hits=false

Also reports document count and on-disk index size.

Usage:  OPENSEARCH_PORT=9200 python -m scripts.bench_search --iters 60
"""
import argparse
import os
import statistics
import time
from datetime import datetime, timedelta

from opensearchpy import OpenSearch

INDEX = "logs"


def client() -> OpenSearch:
    return OpenSearch(
        hosts=[{"host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200"))}],
        http_auth=None, use_ssl=False, verify_certs=False, timeout=120,
    )


def _clauses(scenario):
    """Return (scored_clauses, filter_clauses) for a scenario."""
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    if scenario == "free_text":
        return [{"match": {"message": "timeout"}}], []
    if scenario == "filter_service_level":
        return [], [{"term": {"service": "payment"}}, {"term": {"level": "ERROR"}}]
    if scenario == "filter_time_range":
        return [], [{"term": {"service": "auth"}},
                    {"range": {"timestamp": {"gte": since}}}]
    if scenario == "combined":
        return ([{"match": {"message": "error"}}],
                [{"term": {"service": "checkout"}}, {"term": {"level": "ERROR"}},
                 {"range": {"timestamp": {"gte": since}}}])
    raise ValueError(scenario)


def build_query(scenario, optimized):
    scored, filters = _clauses(scenario)
    if optimized:
        body = {"query": {"bool": {"must": scored or [{"match_all": {}}],
                                   "filter": filters}},
                "track_total_hits": False}
    else:  # baseline: everything in must
        body = {"query": {"bool": {"must": (scored + filters) or [{"match_all": {}}]}}}
    body["sort"] = [{"timestamp": {"order": "desc"}}]
    body["size"] = 50
    return body


def measure(c, scenario, optimized, iters):
    latencies = []
    for _ in range(iters):
        body = build_query(scenario, optimized)
        t0 = time.perf_counter()
        c.search(index=INDEX, body=body)
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    return p50, p95


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--warmup", type=int, default=5)
    args = ap.parse_args()
    c = client()

    count = c.count(index=INDEX)["count"]
    size_bytes = c.indices.stats(index=INDEX)["_all"]["primaries"]["store"]["size_in_bytes"]

    print("\n" + "=" * 70)
    print(f"SEARCH LATENCY  @  {count:,} documents   (index size {size_bytes/1e6:,.0f} MB)")
    print("=" * 70)
    print(f"{'scenario':<24}{'baseline p50/p95':>20}{'optimized p50/p95':>22}")
    print("-" * 70)
    scenarios = ["free_text", "filter_service_level", "filter_time_range", "combined"]
    for sc in scenarios:
        for opt in (False, True):  # warm each shape's caches
            for _ in range(args.warmup):
                c.search(index=INDEX, body=build_query(sc, opt))
        b50, b95 = measure(c, sc, False, args.iters)
        o50, o95 = measure(c, sc, True, args.iters)
        print(f"{sc:<24}{f'{b50:.0f}/{b95:.0f} ms':>20}{f'{o50:.0f}/{o95:.0f} ms':>22}")
    print("=" * 70)

    _bench_pagination(c, args.iters)


def _timeit(c, body, n):
    lat = []
    for _ in range(n):
        t = time.perf_counter()
        c.search(index=INDEX, body=body)
        lat.append((time.perf_counter() - t) * 1000)
    lat.sort()
    return statistics.median(lat), lat[max(0, int(n * 0.95) - 1)]


def _bench_pagination(c, iters):
    """The slowest pattern: deep from/size pagination vs a search_after cursor."""
    sort = [{"timestamp": {"order": "desc"}}, {"_id": {"order": "asc"}}]
    print("\nDEEP PAGINATION  (from/size is capped at from+size<=10000)")
    print("-" * 70)
    print(f"{'strategy':<28}{'p50':>10}{'p95':>10}")
    for frm in (0, 2000, 5000, 9950):
        p50, p95 = _timeit(c, {"query": {"match_all": {}}, "sort": sort,
                               "size": 50, "from": frm}, iters)
        print(f"{f'from={frm}':<28}{f'{p50:.0f} ms':>10}{f'{p95:.0f} ms':>10}")
    cur = c.search(index=INDEX, body={"query": {"match_all": {}}, "sort": sort,
                                      "size": 50, "from": 9950})["hits"]["hits"][-1]["sort"]
    p50, p95 = _timeit(c, {"query": {"match_all": {}}, "sort": sort,
                           "size": 50, "search_after": cur}, iters)
    print(f"{'search_after (any depth)':<28}{f'{p50:.0f} ms':>10}{f'{p95:.0f} ms':>10}")
    print("=" * 70)


if __name__ == "__main__":
    main()
