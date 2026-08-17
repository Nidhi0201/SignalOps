"""Search filters, combinations, free-text, time window, sort order."""
import pytest

pytestmark = pytest.mark.integration


CORPUS = [
    {"service": "payment", "level": "ERROR", "message": "gateway timeout",
     "timestamp": "2026-01-15T10:00:00Z"},
    {"service": "payment", "level": "INFO", "message": "charge succeeded",
     "timestamp": "2026-01-15T11:00:00Z"},
    {"service": "auth", "level": "ERROR", "message": "invalid token signature",
     "timestamp": "2026-01-15T12:00:00Z"},
    {"service": "auth", "level": "WARN", "message": "token near expiry",
     "timestamp": "2026-01-16T09:00:00Z"},
    {"service": "billing", "level": "ERROR", "message": "gateway timeout retry",
     "timestamp": "2026-01-16T10:00:00Z"},
]


@pytest.fixture
def corpus(seed_logs):
    return seed_logs(CORPUS)


def test_no_filters_returns_all(corpus, client):
    hits = client.get("/logs/search").json()
    assert len(hits) == len(CORPUS)


def test_filter_by_service(corpus, client):
    hits = client.get("/logs/search", params={"service": "payment"}).json()
    assert len(hits) == 2
    assert {h["service"] for h in hits} == {"payment"}


def test_filter_by_level(corpus, client):
    hits = client.get("/logs/search", params={"level": "ERROR"}).json()
    assert len(hits) == 3
    assert {h["level"] for h in hits} == {"ERROR"}


def test_free_text_query_matches_message(corpus, client):
    hits = client.get("/logs/search", params={"q": "timeout"}).json()
    # "gateway timeout" and "gateway timeout retry"
    assert len(hits) == 2
    assert all("timeout" in h["message"] for h in hits)


def test_service_and_level_combination(corpus, client):
    hits = client.get(
        "/logs/search", params={"service": "payment", "level": "ERROR"}
    ).json()
    assert len(hits) == 1
    assert hits[0]["message"] == "gateway timeout"


def test_service_level_and_freetext_combination(corpus, client):
    hits = client.get(
        "/logs/search",
        params={"service": "billing", "level": "ERROR", "q": "timeout"},
    ).json()
    assert len(hits) == 1
    assert hits[0]["service"] == "billing"


def test_time_window_from_only(corpus, client):
    hits = client.get(
        "/logs/search", params={"from": "2026-01-16T00:00:00Z"}
    ).json()
    # only the two Jan-16 logs
    assert len(hits) == 2


def test_time_window_to_only(corpus, client):
    hits = client.get(
        "/logs/search", params={"to": "2026-01-15T23:59:59Z"}
    ).json()
    # the three Jan-15 logs
    assert len(hits) == 3


def test_time_window_from_and_to(corpus, client):
    hits = client.get(
        "/logs/search",
        params={"from": "2026-01-15T10:30:00Z", "to": "2026-01-15T12:30:00Z"},
    ).json()
    # 11:00 payment INFO and 12:00 auth ERROR
    assert len(hits) == 2


def test_results_sorted_by_timestamp_desc(corpus, client):
    hits = client.get("/logs/search").json()
    timestamps = [h["timestamp"] for h in hits]
    assert timestamps == sorted(timestamps, reverse=True)


def test_filter_with_no_matches_returns_empty(corpus, client):
    hits = client.get("/logs/search", params={"service": "does-not-exist"}).json()
    assert hits == []
