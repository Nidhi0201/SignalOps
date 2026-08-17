"""
Incident lifecycle endpoints.

Incidents are normally created by the scheduler; here we insert them directly
via SQLAlchemy so we can exercise the list / detail / ack / resolve / update
API without running the background evaluator.
"""
from datetime import datetime

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def rule_and_incident(db_session):
    from app.models import AlertRule, Incident

    rule = AlertRule(
        name="payment errors",
        service="payment",
        level="ERROR",
        window_minutes=5,
        threshold_count=10,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)

    incident = Incident(
        alert_rule_id=rule.id,
        start_time=datetime(2026, 1, 15, 12, 0, 0),
        status="open",
        log_count=15,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return {"rule_id": rule.id, "incident_id": incident.id}


def test_list_incidents(rule_and_incident, client):
    rows = client.get("/alerts/incidents").json()
    assert len(rows) == 1
    assert rows[0]["status"] == "open"
    assert rows[0]["log_count"] == 15


def test_get_incident(rule_and_incident, client):
    iid = rule_and_incident["incident_id"]
    resp = client.get(f"/alerts/incidents/{iid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == iid


def test_get_missing_incident_404(client):
    assert client.get("/alerts/incidents/99999").status_code == 404


def test_filter_incidents_by_status(rule_and_incident, client):
    assert len(client.get("/alerts/incidents", params={"status": "open"}).json()) == 1
    assert client.get("/alerts/incidents", params={"status": "resolved"}).json() == []


def test_filter_incidents_by_rule(rule_and_incident, client):
    rid = rule_and_incident["rule_id"]
    assert len(client.get("/alerts/incidents", params={"alert_rule_id": rid}).json()) == 1
    assert client.get("/alerts/incidents", params={"alert_rule_id": 4242}).json() == []


def test_acknowledge_incident(rule_and_incident, client):
    iid = rule_and_incident["incident_id"]
    resp = client.post(f"/alerts/incidents/{iid}/ack")
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


def test_resolve_incident_sets_end_time(rule_and_incident, client):
    iid = rule_and_incident["incident_id"]
    resp = client.post(f"/alerts/incidents/{iid}/resolve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["end_time"] is not None


def test_update_incident_status(rule_and_incident, client):
    iid = rule_and_incident["incident_id"]
    resp = client.patch(f"/alerts/incidents/{iid}", json={"status": "acknowledged"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


def test_update_missing_incident_404(client):
    assert client.patch("/alerts/incidents/99999", json={"status": "resolved"}).status_code == 404


def test_ack_missing_incident_404(client):
    assert client.post("/alerts/incidents/99999/ack").status_code == 404
