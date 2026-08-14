from __future__ import annotations


def _create(c, title: str) -> str:
    r = c.post("/api/agent/mindmaps", json={"title": title, "outline_md": "# x"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _ids(r) -> list[str]:
    assert r.status_code == 200, r.text
    return [m["id"] for m in r.json()["items"]]


def test_mindmap_date_range_filter(logged_in_client):
    c = logged_in_client
    a = _create(c, "图A")
    b = _create(c, "图B")
    both = {a, b}

    # created_at is "now" (2026); use far-past / far-future bounds so tests are
    # deterministic without crafting timestamps.
    assert both.issubset(set(_ids(c.get("/api/agent/mindmaps?start_date=2000-01-01"))))
    assert _ids(c.get("/api/agent/mindmaps?start_date=2099-01-01")) == []
    assert _ids(c.get("/api/agent/mindmaps?end_date=2000-01-01")) == []
    assert both.issubset(set(_ids(c.get("/api/agent/mindmaps?end_date=2099-12-31"))))


def test_mindmap_combined_range_spanning_today(logged_in_client):
    c = logged_in_client
    a = _create(c, "图A")
    b = _create(c, "图B")
    both = {a, b}

    ids = _ids(c.get("/api/agent/mindmaps?start_date=2000-01-01&end_date=2099-12-31"))
    assert both.issubset(set(ids))
