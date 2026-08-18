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


def test_search_after_cursor_pagination(twenty_logs, client):
    import json

    p1 = client.get("/logs/search", params={"page_size": 5}).json()
    assert len(p1) == 5
    last = p1[-1]
    cursor = json.dumps([last["timestamp"], last["id"]])
    p2 = client.get(
        "/logs/search", params={"page_size": 5, "search_after": cursor}
    ).json()
    assert len(p2) == 5
    # cursor page continues past page 1 with no overlap
    assert {h["id"] for h in p1}.isdisjoint({h["id"] for h in p2})


def test_search_after_covers_every_doc(twenty_logs, client):
    import json

    seen, cursor = [], None
    for _ in range(6):  # 20 docs / 5 per page, plus a final empty page
        params = {"page_size": 5}
        if cursor:
            params["search_after"] = cursor
        page = client.get("/logs/search", params=params).json()
        if not page:
            break
        seen.extend(h["id"] for h in page)
        last = page[-1]
        cursor = json.dumps([last["timestamp"], last["id"]])
    assert len(set(seen)) == 20


def test_invalid_search_after_rejected(twenty_logs, client):
    resp = client.get("/logs/search", params={"search_after": "not-json"})
    assert resp.status_code == 400


def test_full_pagination_covers_every_doc(twenty_logs, client):
    seen = set()
    for page in range(1, 5):  # 4 pages of 5 = 20
        hits = client.get(
            "/logs/search", params={"page": page, "page_size": 5}
        ).json()
        seen.update(h["id"] for h in hits)
    assert len(seen) == 20
