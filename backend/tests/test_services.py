"""GET /logs/services -> distinct, sorted service names via aggregation."""
import pytest

pytestmark = pytest.mark.integration


def test_services_empty_when_no_logs(client):
    assert client.get("/logs/services").json() == []


def test_services_returns_sorted_unique(seed_logs, client):
    seed_logs(
        [
            {"service": "payment", "level": "INFO", "message": "a",
             "timestamp": "2026-01-15T10:00:00Z"},
            {"service": "auth", "level": "INFO", "message": "b",
             "timestamp": "2026-01-15T10:01:00Z"},
            {"service": "payment", "level": "ERROR", "message": "c",
             "timestamp": "2026-01-15T10:02:00Z"},
            {"service": "billing", "level": "WARN", "message": "d",
             "timestamp": "2026-01-15T10:03:00Z"},
        ]
    )
    services = client.get("/logs/services").json()
    assert services == ["auth", "billing", "payment"]
