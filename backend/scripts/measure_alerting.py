"""
Alerting measurement harness.

Generates a LABELED log timeline with known fault onsets, indexes it into
OpenSearch, then replays the polling evaluator over a virtual clock and measures:

  * detection latency  = (incident opened tick) - (fault onset), per rule type
  * false-positive rate = incidents opened while no fault was active

The virtual clock makes results reproducible and lets us honestly attribute
latency to (poll interval, window, for_consecutive) rather than wall-clock noise.
Run repeatedly with randomized fault phase to get a latency distribution.

Usage (needs OpenSearch + Postgres reachable):
    OPENSEARCH_HOST=localhost OPENSEARCH_PORT=9200 \
    DATABASE_URL=postgresql://signalops:signalops@localhost:5432/signalops \
    python -m scripts.measure_alerting --trials 20 --interval 15
"""
import argparse
import os
import random
import statistics
from datetime import datetime, timedelta

from opensearchpy import OpenSearch, helpers
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.alert_engine import evaluate_all_rules
from app.database import Base
from app.models import AlertRule, Incident

BASE = datetime(2026, 1, 1, 0, 0, 0)
DURATION_S = 600          # 10 virtual minutes per trial
WINDOW_MIN = 2            # rule sliding window
FAULT_LEN_S = 180         # each fault lasts 3 minutes
LOGS_INDEX = "logs"

MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "service": {"type": "keyword"},
            "level": {"type": "keyword"},
            "message": {"type": "text"},
        }
    }
}


def os_client() -> OpenSearch:
    return OpenSearch(
        hosts=[{"host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200"))}],
        http_auth=None, use_ssl=False, verify_certs=False, timeout=30,
    )


def reset_index(client):
    if client.indices.exists(index=LOGS_INDEX):
        client.indices.delete(index=LOGS_INDEX)
    client.indices.create(index=LOGS_INDEX, body=MAPPING)


def _log(ts, service, level):
    return {"_index": LOGS_INDEX, "_source": {
        "timestamp": ts.isoformat(), "service": service, "level": level,
        "message": f"{service} {level}"}}


def build_timeline(fault_onsets):
    """Emit a labeled log stream. fault_onsets maps rule->onset seconds."""
    docs = []
    fa, fb, fc = fault_onsets["count"], fault_onsets["error_rate"], fault_onsets["heartbeat"]
    for t in range(0, DURATION_S, 5):  # a sample every 5s
        ts = BASE + timedelta(seconds=t)
        # payment: baseline 1 error / sample (below threshold 5); burst during fault A
        payment_errors = 8 if fa <= t < fa + FAULT_LEN_S else 1
        for _ in range(payment_errors):
            docs.append(_log(ts, "payment", "ERROR"))
        docs.append(_log(ts, "payment", "INFO"))
        # api: baseline ~10% errors; ~70% during fault B (10 logs/sample)
        api_err_ratio = 0.7 if fb <= t < fb + FAULT_LEN_S else 0.1
        for i in range(10):
            docs.append(_log(ts, "api", "ERROR" if i < api_err_ratio * 10 else "INFO"))
        # worker: heartbeat every sample, silent during fault C
        if not (fc <= t < fc + FAULT_LEN_S):
            docs.append(_log(ts, "worker", "INFO"))
    return docs


def make_rules(db):
    db.query(Incident).delete()
    db.query(AlertRule).delete()
    db.commit()
    rules = {
        # threshold 60 sits above baseline (~24 errors/window) and well below the
        # fault burst (~192 errors/window), so baseline noise does not trip it.
        "count": AlertRule(name="payment-errors", service="payment", level="ERROR",
                           window_minutes=WINDOW_MIN, rule_type="count", threshold_count=60,
                           for_consecutive=1, resolve_after_clear=2, cooldown_minutes=1),
        "error_rate": AlertRule(name="api-error-rate", service="api",
                                window_minutes=WINDOW_MIN, rule_type="error_rate",
                                threshold_count=30, threshold_value=50.0,
                                for_consecutive=1, resolve_after_clear=2, cooldown_minutes=1),
        "heartbeat": AlertRule(name="worker-silence", service="worker",
                               window_minutes=WINDOW_MIN, rule_type="heartbeat_absence",
                               threshold_count=1, for_consecutive=1,
                               resolve_after_clear=2, cooldown_minutes=1),
    }
    for r in rules.values():
        db.add(r)
    db.commit()
    for r in rules.values():
        db.refresh(r)
    return {k: r.id for k, r in rules.items()}


def run_trial(client, db, interval_s, rng):
    # Random fault onsets, spaced so they don't overlap in the timeline.
    # Faults are on different services, so onset windows may overlap freely.
    # Each onset leaves >= window + interval of timeline after it so detection
    # (which for absence needs a full clear window) always fits before the end.
    onsets = {
        "count": rng.randint(60, 150),
        "error_rate": rng.randint(180, 260),
        "heartbeat": rng.randint(280, 380),
    }
    reset_index(client)
    helpers.bulk(client, build_timeline(onsets))
    client.indices.refresh(index=LOGS_INDEX)
    rule_ids = make_rules(db)

    # Replay ticks over the virtual clock.
    latencies, false_positives, tick_count = {}, 0, 0
    for t in range(0, DURATION_S, interval_s):
        now = BASE + timedelta(seconds=t)
        evaluate_all_rules(db, client, now)
        tick_count += 1

    # Analyze incidents that opened.
    for kind, rid in rule_ids.items():
        onset = onsets[kind]
        fault_end = onset + FAULT_LEN_S
        incidents = db.query(Incident).filter(Incident.alert_rule_id == rid).all()
        detected = None
        for inc in incidents:
            opened_s = (inc.start_time - BASE).total_seconds()
            # An incident whose open tick falls in the fault window (+ window lag
            # for absence detection) is a true detection; else a false positive.
            lag_allow = WINDOW_MIN * 60 + interval_s
            if onset <= opened_s <= fault_end + lag_allow:
                if detected is None or opened_s < detected:
                    detected = opened_s
            else:
                false_positives += 1
        if detected is not None:
            latencies[kind] = detected - onset
    return latencies, false_positives, tick_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--interval", type=int, default=15, help="poll interval (virtual seconds)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    client = os_client()
    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://signalops:signalops@localhost:5432/signalops"))
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    rng = random.Random(args.seed)

    per_kind = {"count": [], "error_rate": [], "heartbeat": []}
    total_fp, total_ticks = 0, 0
    for _ in range(args.trials):
        db = Session()
        try:
            lat, fp, ticks = run_trial(client, db, args.interval, rng)
            for k, v in lat.items():
                per_kind[k].append(v)
            total_fp += fp
            total_ticks += ticks
        finally:
            db.close()

    print("\n" + "=" * 60)
    print(f"ALERTING MEASUREMENT  ({args.trials} trials, poll interval {args.interval}s, "
          f"window {WINDOW_MIN}m)")
    print("=" * 60)
    print(f"{'rule type':<18}{'detections':>11}{'median':>9}{'p95':>8}  (detection latency, s)")
    for kind, vals in per_kind.items():
        if vals:
            med = statistics.median(vals)
            p95 = sorted(vals)[max(0, int(len(vals) * 0.95) - 1)]
            print(f"{kind:<18}{len(vals):>11}{med:>9.0f}{p95:>8.0f}")
        else:
            print(f"{kind:<18}{'0':>11}{'—':>9}{'—':>8}  (never detected!)")
    all_lat = [v for vals in per_kind.values() for v in vals]
    if all_lat:
        print("-" * 60)
        print(f"{'OVERALL':<18}{len(all_lat):>11}{statistics.median(all_lat):>9.0f}"
              f"{sorted(all_lat)[max(0, int(len(all_lat) * 0.95) - 1)]:>8.0f}")
    fp_rate = total_fp / total_ticks * 100 if total_ticks else 0
    print(f"\nFalse positives: {total_fp} spurious incidents over {total_ticks} evaluation "
          f"ticks = {fp_rate:.2f}% FP rate")
    print("=" * 60)


if __name__ == "__main__":
    main()
