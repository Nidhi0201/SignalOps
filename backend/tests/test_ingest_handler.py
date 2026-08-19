"""Unit tests for the serverless ingestion Lambda (no AWS, no containers)."""
import base64
import json

import pytest

from lambdas import ingest_handler as h

pytestmark = pytest.mark.unit


class FakeRedis:
    def __init__(self):
        self.entries = []
        self.last_kwargs = None

    def xadd(self, stream, fields, maxlen=None, approximate=None):
        self.last_kwargs = {"maxlen": maxlen, "approximate": approximate}
        eid = f"{len(self.entries) + 1}-0"
        self.entries.append((stream, fields))
        return eid


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fr = FakeRedis()
    monkeypatch.setattr(h, "_client", fr)
    monkeypatch.setattr(h, "_get_client", lambda: fr)
    return fr


def _event(body, b64=False):
    return {"body": body, "isBase64Encoded": b64}


def _log(**over):
    base = {"service": "s", "level": "INFO", "message": "x"}
    base.update(over)
    return base


def test_single_log_returns_202(fake_redis):
    resp = h.handler(_event(json.dumps(_log())))
    assert resp["statusCode"] == 202
    body = json.loads(resp["body"])
    assert body["accepted"] == 1
    assert len(fake_redis.entries) == 1
    assert fake_redis.entries[0][0] == h.LOG_STREAM


def test_batch(fake_redis):
    resp = h.handler(_event(json.dumps([_log(message=f"m{i}") for i in range(4)])))
    assert json.loads(resp["body"])["accepted"] == 4
    assert len(fake_redis.entries) == 4


def test_bad_json_returns_400(fake_redis):
    resp = h.handler(_event("not json"))
    assert resp["statusCode"] == 400
    assert fake_redis.entries == []


def test_validation_error_returns_422(fake_redis):
    resp = h.handler(_event(json.dumps({"service": "s", "level": "NOPE", "message": "x"})))
    assert resp["statusCode"] == 422
    assert fake_redis.entries == []


def test_missing_field_returns_422(fake_redis):
    resp = h.handler(_event(json.dumps({"level": "INFO", "message": "x"})))
    assert resp["statusCode"] == 422


def test_base64_encoded_body(fake_redis):
    encoded = base64.b64encode(json.dumps(_log()).encode()).decode()
    resp = h.handler(_event(encoded, b64=True))
    assert resp["statusCode"] == 202
    assert len(fake_redis.entries) == 1


def test_stream_is_bounded(fake_redis):
    h.handler(_event(json.dumps(_log())))
    assert fake_redis.last_kwargs["approximate"] is True
    assert fake_redis.last_kwargs["maxlen"] == h.LOG_STREAM_MAXLEN


def test_payload_serialized_as_json_data_field(fake_redis):
    h.handler(_event(json.dumps(_log(message="hello"))))
    _stream, fields = fake_redis.entries[0]
    assert "data" in fields
    assert json.loads(fields["data"])["message"] == "hello"
