from __future__ import annotations


def test_create_list_get_update_delete_mindmap(logged_in_client):
    c = logged_in_client
    r = c.post("/api/agent/mindmaps",
               json={"title": "现在完成时", "outline_md": "# 现在完成时\n## 结构"})
    assert r.status_code == 200, r.text
    mid = r.json()["id"]

    r = c.get("/api/agent/mindmaps")
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()["items"]]
    assert mid in ids

    r = c.get(f"/api/agent/mindmaps/{mid}")
    assert r.status_code == 200
    assert r.json()["outline_md"].startswith("# 现在完成时")

    r = c.patch(f"/api/agent/mindmaps/{mid}",
                json={"title": "新名", "outline_md": "# 新名\n## 用法"})
    assert r.status_code == 200
    r = c.get(f"/api/agent/mindmaps/{mid}")
    assert r.json()["title"] == "新名" and r.json()["outline_md"].endswith("## 用法")

    r = c.delete(f"/api/agent/mindmaps/{mid}")
    assert r.status_code == 204
    r = c.get(f"/api/agent/mindmaps/{mid}")
    assert r.status_code == 404


def test_mindmap_isolation_between_users(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})
    ra = client.post("/api/agent/mindmaps", json={"title": "A图", "outline_md": "# A"})
    assert ra.status_code == 200, ra.text
    mid = ra.json()["id"]
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"username": "bob", "password": "pw123456"})
    rb = client.get(f"/api/agent/mindmaps/{mid}")
    assert rb.status_code == 404
