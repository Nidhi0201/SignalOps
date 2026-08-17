"""Alert-rule CRUD against real Postgres (SQLAlchemy layer)."""
import pytest

pytestmark = pytest.mark.integration


def _rule(**over):
    base = {
        "name": "payment errors",
        "service": "payment",
        "level": "ERROR",
        "window_minutes": 5,
        "threshold_count": 10,
    }
    base.update(over)
    return base


def test_create_rule(client):
    resp = client.post("/alerts", json=_rule())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] >= 1
    assert body["name"] == "payment errors"
    assert body["enabled"] is True
    assert body["org_id"] == "default"


def test_get_rule(client):
    rid = client.post("/alerts", json=_rule()).json()["id"]
    resp = client.get(f"/alerts/{rid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == rid


def test_get_missing_rule_404(client):
    assert client.get("/alerts/99999").status_code == 404


def test_list_rules(client):
    client.post("/alerts", json=_rule(name="a"))
    client.post("/alerts", json=_rule(name="b"))
    rows = client.get("/alerts").json()
    assert len(rows) == 2


def test_list_filter_by_enabled(client):
    rid = client.post("/alerts", json=_rule(name="on")).json()["id"]
    client.post(f"/alerts/{rid}/toggle")  # now disabled
    client.post("/alerts", json=_rule(name="still-on"))
    enabled = client.get("/alerts", params={"enabled": "true"}).json()
    disabled = client.get("/alerts", params={"enabled": "false"}).json()
    assert {r["name"] for r in enabled} == {"still-on"}
    assert {r["name"] for r in disabled} == {"on"}


def test_update_rule(client):
    rid = client.post("/alerts", json=_rule()).json()["id"]
    resp = client.patch(f"/alerts/{rid}", json={"threshold_count": 42})
    assert resp.status_code == 200
    assert resp.json()["threshold_count"] == 42


def test_update_missing_rule_404(client):
    assert client.patch("/alerts/99999", json={"threshold_count": 1}).status_code == 404


def test_toggle_rule(client):
    rid = client.post("/alerts", json=_rule()).json()["id"]
    assert client.post(f"/alerts/{rid}/toggle").json()["enabled"] is False
    assert client.post(f"/alerts/{rid}/toggle").json()["enabled"] is True


def test_delete_rule(client):
    rid = client.post("/alerts", json=_rule()).json()["id"]
    assert client.delete(f"/alerts/{rid}").status_code == 204
    assert client.get(f"/alerts/{rid}").status_code == 404


def test_delete_missing_rule_404(client):
    assert client.delete("/alerts/99999").status_code == 404


def test_window_minutes_must_be_positive(client):
    assert client.post("/alerts", json=_rule(window_minutes=0)).status_code == 422


def test_threshold_count_must_be_positive(client):
    assert client.post("/alerts", json=_rule(threshold_count=0)).status_code == 422


def test_incidents_endpoint_is_reachable(client):
    """
    Regression: GET /alerts/incidents was shadowed by GET /alerts/{rule_id}
    and returned 422. With the :int path converter it resolves correctly.
    """
    resp = client.get("/alerts/incidents")
    assert resp.status_code == 200
    assert resp.json() == []
