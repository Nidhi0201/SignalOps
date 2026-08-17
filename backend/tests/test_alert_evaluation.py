"""
End-to-end evaluation against real OpenSearch + Postgres:
the three rule types and the flap-damping lifecycle.
"""
from datetime import datetime, timedelta

import pytest

from app.alert_engine import evaluate_all_rules
from app.models import AlertRule, Incident

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 15, 12, 0, 0)
IN_WINDOW = (NOW - timedelta(minutes=1)).isoformat()  # naive UTC, inside a 5-min window


def _log(service, level, i=0):
    return {
        "service": service,
        "level": level,
        "message": f"{service} {level} {i}",
        "timestamp": IN_WINDOW,
    }


def _add_rule(db, **over):
    base = dict(
        name="r", service="payment", level="ERROR", window_minutes=5,
        rule_type="count", threshold_count=3, for_consecutive=1,
        resolve_after_clear=1, cooldown_minutes=5, enabled=True,
    )
    base.update(over)
    rule = AlertRule(**base)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def _open_incidents(db, rule_id):
    return db.query(Incident).filter(
        Incident.alert_rule_id == rule_id, Incident.status == "open"
    ).all()


# --- rule types --------------------------------------------------------------
def test_count_rule_opens_incident(seed_logs, opensearch_client, db_session):
    seed_logs([_log("payment", "ERROR", i) for i in range(4)])
    rule = _add_rule(db_session, threshold_count=3)
    evaluate_all_rules(db_session, opensearch_client, NOW)
    assert len(_open_incidents(db_session, rule.id)) == 1


def test_count_rule_below_threshold_no_incident(seed_logs, opensearch_client, db_session):
    seed_logs([_log("payment", "ERROR", i) for i in range(2)])  # 2 < 3
    rule = _add_rule(db_session, threshold_count=3)
    evaluate_all_rules(db_session, opensearch_client, NOW)
    assert _open_incidents(db_session, rule.id) == []


def test_error_rate_rule_opens(seed_logs, opensearch_client, db_session):
    logs = [_log("api", "ERROR", i) for i in range(6)] + [_log("api", "INFO", i) for i in range(4)]
    seed_logs(logs)  # 6/10 = 60% error rate
    rule = _add_rule(
        db_session, name="er", service="api", level=None,
        rule_type="error_rate", threshold_count=5, threshold_value=50,
    )
    evaluate_all_rules(db_session, opensearch_client, NOW)
    assert len(_open_incidents(db_session, rule.id)) == 1


def test_error_rate_below_min_volume_no_incident(seed_logs, opensearch_client, db_session):
    seed_logs([_log("api", "ERROR", 0), _log("api", "ERROR", 1)])  # 100% but only 2 logs
    rule = _add_rule(
        db_session, name="er", service="api", level=None,
        rule_type="error_rate", threshold_count=5, threshold_value=50,
    )
    evaluate_all_rules(db_session, opensearch_client, NOW)
    assert _open_incidents(db_session, rule.id) == []  # min-volume guard


def test_heartbeat_absence_opens_when_silent(seed_logs, opensearch_client, db_session):
    seed_logs([_log("other", "INFO", 0)])  # worker produced nothing
    rule = _add_rule(
        db_session, name="hb", service="worker", level=None,
        rule_type="heartbeat_absence", threshold_count=1,
    )
    evaluate_all_rules(db_session, opensearch_client, NOW)
    assert len(_open_incidents(db_session, rule.id)) == 1


def test_heartbeat_present_no_incident(seed_logs, opensearch_client, db_session):
    seed_logs([_log("worker", "INFO", 0)])  # worker is alive
    rule = _add_rule(
        db_session, name="hb", service="worker", level=None,
        rule_type="heartbeat_absence", threshold_count=1,
    )
    evaluate_all_rules(db_session, opensearch_client, NOW)
    assert _open_incidents(db_session, rule.id) == []


# --- flap damping ------------------------------------------------------------
def test_for_consecutive_delays_open(seed_logs, opensearch_client, db_session):
    seed_logs([_log("payment", "ERROR", i) for i in range(4)])
    rule = _add_rule(db_session, threshold_count=3, for_consecutive=2)
    evaluate_all_rules(db_session, opensearch_client, NOW)  # 1st breach
    assert _open_incidents(db_session, rule.id) == []
    evaluate_all_rules(db_session, opensearch_client, NOW)  # 2nd breach -> open
    assert len(_open_incidents(db_session, rule.id)) == 1


def test_dedup_no_second_incident(seed_logs, opensearch_client, db_session):
    seed_logs([_log("payment", "ERROR", i) for i in range(4)])
    rule = _add_rule(db_session, threshold_count=3, for_consecutive=1)
    evaluate_all_rules(db_session, opensearch_client, NOW)
    evaluate_all_rules(db_session, opensearch_client, NOW)
    all_incidents = db_session.query(Incident).filter(Incident.alert_rule_id == rule.id).all()
    assert len(all_incidents) == 1


def test_auto_resolve_when_condition_clears(seed_logs, opensearch_client, db_session):
    seed_logs([_log("payment", "ERROR", i) for i in range(4)])
    rule = _add_rule(db_session, threshold_count=3, for_consecutive=1, resolve_after_clear=1)
    evaluate_all_rules(db_session, opensearch_client, NOW)
    assert len(_open_incidents(db_session, rule.id)) == 1

    # A later window where the logs have aged out -> not breaching -> resolve.
    later = NOW + timedelta(minutes=10)
    evaluate_all_rules(db_session, opensearch_client, later)
    assert _open_incidents(db_session, rule.id) == []
    resolved = db_session.query(Incident).filter(
        Incident.alert_rule_id == rule.id, Incident.status == "resolved"
    ).all()
    assert len(resolved) == 1
    assert resolved[0].end_time is not None
