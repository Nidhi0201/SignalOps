"""
Ingestion benchmark: synchronous path vs async Redis-Streams path.

Measures, against a running API:
  * sustained ingestion throughput (logs/sec) for /logs/ingest/sync vs /logs/ingest
  * p95 end-to-end latency (POST -> searchable in OpenSearch) for the async path

The async endpoint returns after XADD, so "searchable" is measured by polling
GET /logs/search for a unique per-probe marker until the document appears.

Usage (needs API + Redis + OpenSearch + a running consumer):
    python -m scripts.benchmark_ingest --base http://localhost:8000 --n 5000 --batch 50 --concurrency 16
"""
import argparse
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx


def _log(msg):
    return {"service": "bench", "level": "INFO", "message": msg,
            "timestamp": "2026-01-15T12:00:00Z"}


def _throughput(base, endpoint, n, batch, concurrency):
    batches = [[_log(f"bulk {i}-{j}") for j in range(batch)]
               for i in range(0, n, batch)]
    def _send(b):
        try:
            return c.post(endpoint, json=b).status_code < 300
        except Exception:
            return False

    with httpx.Client(base_url=base, timeout=30) as c:
        c.post(endpoint, json=[_log("warmup")])  # prime client/index before timing
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            oks = list(pool.map(_send, batches))
        elapsed = time.perf_counter() - start
    ok_logs = sum(oks) * batch
    return ok_logs, len(batches) * batch, elapsed, ok_logs / elapsed if elapsed else 0


def _e2e_latency(base, probes, poll_timeout=30.0):
    """POST unique probes one at a time, poll search until visible, record latency."""
    latencies = []
    with httpx.Client(base_url=base, timeout=30) as c:
        for _ in range(probes):
            # single opaque token (no separator) so the analyzer can't cross-match
            # one probe's marker against another probe's document.
            marker = "p" + uuid.uuid4().hex
            t0 = time.perf_counter()
            r = c.post("/logs/ingest", json=_log(marker))
            r.raise_for_status()
            deadline = t0 + poll_timeout
            while time.perf_counter() < deadline:
                hits = c.get("/logs/search", params={"q": marker}).json()
                if isinstance(hits, list) and hits:
                    latencies.append(time.perf_counter() - t0)
                    break
                time.sleep(0.05)
            else:
                latencies.append(float("nan"))
    return latencies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--probes", type=int, default=50)
    args = ap.parse_args()

    print(f"\nThroughput: {args.n} logs, batch={args.batch}, concurrency={args.concurrency}")
    print("-" * 56)
    results = {}
    for label, endpoint in [("sync  (/logs/ingest/sync)", "/logs/ingest/sync"),
                            ("async (/logs/ingest)", "/logs/ingest")]:
        ok, total, elapsed, rate = _throughput(args.base, endpoint, args.n, args.batch, args.concurrency)
        results[label] = rate
        note = "" if ok == total else f"  ({total - ok} failed)"
        print(f"{label:<28} {ok:>7}/{total} logs in {elapsed:6.2f}s = {rate:8.0f} logs/sec{note}")
    speedup = results["async (/logs/ingest)"] / results["sync  (/logs/ingest/sync)"]
    print(f"\nAsync is {speedup:.1f}x the synchronous ingestion throughput.")

    print(f"\nEnd-to-end latency (async POST -> searchable), {args.probes} probes")
    print("-" * 56)
    lat = [x for x in _e2e_latency(args.base, args.probes) if x == x]  # drop NaN
    if lat:
        lat.sort()
        p50 = statistics.median(lat)
        p95 = lat[max(0, int(len(lat) * 0.95) - 1)]
        print(f"  detected {len(lat)}/{args.probes}   p50 {p50*1000:6.0f} ms   p95 {p95*1000:6.0f} ms")
    else:
        print("  no probes became searchable (is a consumer running?)")


if __name__ == "__main__":
    main()
