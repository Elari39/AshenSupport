from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Run, SessionLocal, Ticket, now
from app.knowledge import import_document, index_one
from app.main import app
from app.worker import claim, run_claim


def submit(client, scenario="rag"):
    response = client.post(
        "/api/v1/tasks",
        json={"project_id": "notes-of-ashen", "message": "RAG 无法问答", "scenario": scenario},
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def finish(client, task_id):
    claimed = claim()
    assert claimed
    run_claim(claimed)
    return client.get(f"/api/v1/tasks/{task_id}").json()


def seed_document():
    with SessionLocal.begin() as db:
        import_document(
            db, "notes-of-ashen", "rag.md", "# RAG\n\nRAG 问答需要 Qdrant 向量索引和能力开关。", "v1", ""
        )
    assert index_one()


def test_support_approval_is_idempotent(client):
    seed_document()
    task_id = submit(client)
    detail = finish(client, task_id)
    assert detail["status"] == "completed", detail
    assert detail["citations"]
    draft = client.post(f"/api/v1/tasks/{task_id}/ticket-draft").json()
    body = {"version": 1, "decision": "approve", "idempotency_key": "test-key-123"}
    first = client.post(f"/api/v1/ticket-drafts/{draft['id']}/decision", json=body)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/ticket-drafts/{draft['id']}/decision", json=body)
    assert second.json() == first.json()
    body["decision"] = "reject"
    assert client.post(f"/api/v1/ticket-drafts/{draft['id']}/decision", json=body).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Ticket)) == 1


def test_csrf_origin_and_isolation(client):
    task_id = submit(client)
    with TestClient(app, headers={"Origin": "http://testserver"}) as other:
        other.post("/api/v1/sessions/guest")
        assert other.get(f"/api/v1/tasks/{task_id}").status_code == 404
        assert other.get(f"/api/v1/tasks/{task_id}/events").status_code == 404
    assert (
        client.post(f"/api/v1/tasks/{task_id}/cancel", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    )
    assert (
        client.post(f"/api/v1/tasks/{task_id}/cancel", headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    assert client.get("/api/v1/admin/documents").status_code == 403


def test_clarification_has_upper_bound(client):
    task_id = submit(client, "unknown")
    for _ in range(3):
        result = finish(client, task_id)
        assert result["status"] == "waiting_input"
        response = client.post(f"/api/v1/tasks/{task_id}/messages", json={"message": "暂时没有其他信息"})
        assert response.status_code == 202
    assert finish(client, task_id)["status"] == "completed"


def test_cancellation_fences_old_worker(client):
    task_id = submit(client)
    claimed = claim()
    assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 200
    run_claim(claimed)
    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "cancelled"


def test_expired_lease_reclaimed(client):
    task_id = submit(client)
    old = claim()
    with SessionLocal.begin() as db:
        run = db.get(Run, old[0])
        run.lease_until = now() - timedelta(seconds=1)
    new = claim()
    assert old[1] != new[1]
    run_claim(old)
    run_claim(new)
    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "completed"


def test_rejected_stale_draft_and_sse_replay(client):
    task_id = submit(client)
    finish(client, task_id)
    draft = client.post(f"/api/v1/tasks/{task_id}/ticket-draft").json()
    response = client.patch(
        f"/api/v1/ticket-drafts/{draft['id']}",
        json={"version": 1, "title": "修改后标题", "description": "内容"},
    )
    assert response.json()["version"] == 2
    assert (
        client.post(
            f"/api/v1/ticket-drafts/{draft['id']}/decision",
            json={"version": 1, "decision": "approve", "idempotency_key": "stale-key"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/ticket-drafts/{draft['id']}/decision",
            json={"version": 2, "decision": "reject", "idempotency_key": "reject-key"},
        ).status_code
        == 200
    )
    events = client.get(f"/api/v1/tasks/{task_id}/events").text
    assert "event: done" in events and "id:" in events
    last = int(events.split("id: ")[-1].splitlines()[0])
    replay = client.get(f"/api/v1/tasks/{task_id}/events", headers={"Last-Event-ID": str(last)}).text
    assert "id:" not in replay
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Ticket)) == 0


def test_guest_live_tool_and_active_task_limits(client):
    assert (
        client.post(
            "/api/v1/tasks",
            json={"project_id": "notes-of-ashen", "message": "test", "mode": "live", "target_id": "a"},
        ).status_code
        == 403
    )
    submit(client)
    assert (
        client.post("/api/v1/tasks", json={"project_id": "notes-of-ashen", "message": "second"}).status_code
        == 409
    )


def test_bad_citation_fails_closed(client, monkeypatch):
    monkeypatch.setattr(
        "app.worker.generate",
        lambda *a, **kw: {"action": "answer", "summary": "invented", "citation_ids": ["invented-id"]},
    )
    task_id = submit(client)
    assert finish(client, task_id)["status"] == "failed"


def test_cancelled_draft_cannot_be_approved(client):
    task_id = submit(client)
    finish(client, task_id)
    draft = client.post(f"/api/v1/tasks/{task_id}/ticket-draft").json()
    client.post(f"/api/v1/tasks/{task_id}/cancel")
    assert (
        client.post(
            f"/api/v1/ticket-drafts/{draft['id']}/decision",
            json={"version": 1, "decision": "approve", "idempotency_key": "cancel-key"},
        ).status_code
        == 409
    )


def test_concurrent_approval_postgres(client):
    from concurrent.futures import ThreadPoolExecutor

    from app.db import engine

    if engine.dialect.name != "postgresql":
        import pytest

        pytest.skip("Row-lock contention requires PostgreSQL")
    task_id = submit(client)
    finish(client, task_id)
    draft = client.post(f"/api/v1/tasks/{task_id}/ticket-draft").json()
    cookies = dict(client.cookies)
    headers = dict(client.headers)

    def approve(_):
        with TestClient(app, headers=headers, cookies=cookies) as c:
            return c.post(
                f"/api/v1/ticket-drafts/{draft['id']}/decision",
                json={"version": 1, "decision": "approve", "idempotency_key": "parallel-key"},
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(approve, range(4)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert len({r.json()["ticket_id"] for r in results}) == 1


def test_single_session_creation_postgres(client):
    from concurrent.futures import ThreadPoolExecutor

    from app.db import engine

    if engine.dialect.name != "postgresql":
        import pytest

        pytest.skip("Requires PostgreSQL")

    def create(_):
        with TestClient(app, headers=dict(client.headers), cookies=dict(client.cookies)) as c:
            return c.post(
                "/api/v1/tasks", json={"project_id": "notes-of-ashen", "message": "parallel"}
            ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(create, range(4)))
    assert results.count(202) == 1
    assert results.count(409) == 3
