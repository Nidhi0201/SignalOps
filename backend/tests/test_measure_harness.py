"""Smoke test for the measurement harness so it can't silently bit-rot."""
import random

import pytest

from scripts.measure_alerting import build_timeline, run_trial

pytestmark = pytest.mark.integration


def test_build_timeline_emits_all_services():
    docs = build_timeline({"count": 60, "error_rate": 180, "heartbeat": 280})
    services = {d["_source"]["service"] for d in docs}
    assert services == {"payment", "api", "worker"}
    assert len(docs) > 100


def test_run_trial_detects_faults(opensearch_client, db_session):
    latencies, false_positives, ticks = run_trial(
        opensearch_client, db_session, interval_s=15, rng=random.Random(1)
    )
    # All three injected faults should be detected, with no spurious incidents.
    assert set(latencies.keys()) == {"count", "error_rate", "heartbeat"}
    assert all(v >= 0 for v in latencies.values())
    assert false_positives == 0
    assert ticks > 0
