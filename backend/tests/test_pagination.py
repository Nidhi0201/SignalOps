"""Pagination: page/page_size behaviour and edge cases."""
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def twenty_logs(seed_logs):
    # Distinct, ordered timestamps so paging is deterministic.
    logs = [
        {
            "service": "svc",
            "level": "INFO",
            "message": f"msg {i:02d}",
            "timestamp": f"2026-01-15T10:{i:02d}:00Z",
        }
        for i in range(20)
    ]
    return seed_logs(logs)


def test_first_page_size(twenty_logs, client):
    hits = client.get("/logs/search", params={"page": 1, "page_size": 5}).json()
    assert len(hits) == 5


def test_second_page_is_disjoint_from_first(twenty_logs, client):
    p1 = client.get("/logs/search", params={"page": 1, "page_size": 5}).json()
    p2 = client.get("/logs/search", params={"page": 2, "page_size": 5}).json()
    ids1 = {h["id"] for h in p1}
    ids2 = {h["id"] for h in p2}
    assert ids1.isdisjoint(ids2)
    assert len(ids2) == 5


def test_page_beyond_data_is_empty(twenty_logs, client):
    hits = client.get("/logs/search", params={"page": 99, "page_size": 5}).json()
    assert hits == []


def test_page_size_larger_than_corpus_returns_all(twenty_logs, client):
    hits = client.get("/logs/search", params={"page": 1, "page_size": 100}).json()
    assert len(hits) == 20


def test_page_zero_rejected(twenty_logs, client):
    resp = client.get("/logs/search", params={"page": 0, "page_size": 5})
    assert resp.status_code == 400


def test_negative_page_rejected(twenty_logs, client):
    resp = client.get("/logs/search", params={"page": -1, "page_size": 5})
    assert resp.status_code == 400


def test_full_pagination_covers_every_doc(twenty_logs, client):
    seen = set()
    for page in range(1, 5):  # 4 pages of 5 = 20
        hits = client.get(
            "/logs/search", params={"page": page, "page_size": 5}
        ).json()
        seen.update(h["id"] for h in hits)
    assert len(seen) == 20
