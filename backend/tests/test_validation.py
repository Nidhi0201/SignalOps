"""Malformed ingest payloads must be rejected with 422 (Pydantic validation)."""
import pytest

pytestmark = pytest.mark.integration


def test_missing_service_rejected(client):
    resp = client.post("/logs/ingest", json={"level": "INFO", "message": "x"})
    assert resp.status_code == 422


def test_missing_message_rejected(client):
    resp = client.post("/logs/ingest", json={"service": "s", "level": "INFO"})
    assert resp.status_code == 422


def test_invalid_level_enum_rejected(client):
    resp = client.post(
        "/logs/ingest",
        json={"service": "s", "level": "CRITICAL", "message": "x"},
    )
    assert resp.status_code == 422


def test_empty_object_rejected(client):
    resp = client.post("/logs/ingest", json={})
    assert resp.status_code == 422


def test_wrong_metadata_type_rejected(client):
    resp = client.post(
        "/logs/ingest",
        json={"service": "s", "level": "INFO", "message": "x",
              "metadata": "not-a-dict"},
    )
    assert resp.status_code == 422


def test_bad_timestamp_rejected(client):
    resp = client.post(
        "/logs/ingest",
        json={"service": "s", "level": "INFO", "message": "x",
              "timestamp": "not-a-date"},
    )
    assert resp.status_code == 422


def test_batch_with_one_invalid_item_rejected(client):
    resp = client.post(
        "/logs/ingest",
        json=[
            {"service": "s", "level": "INFO", "message": "ok"},
            {"service": "s", "level": "NOPE", "message": "bad"},
        ],
    )
    assert resp.status_code == 422


def test_valid_payload_not_rejected(client):
    resp = client.post(
        "/logs/ingest",
        json={"service": "s", "level": "INFO", "message": "ok"},
    )
    assert resp.status_code == 202
