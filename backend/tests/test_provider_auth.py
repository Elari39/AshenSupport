import pytest
from argon2 import PasswordHasher
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, Usage, User
from app.llm import ProviderError, request_json


@pytest.mark.parametrize("retryable,expected", [(True, 3), (False, 1)])
def test_provider_retries_are_bounded_and_counted(monkeypatch, retryable, expected):
    calls = []

    async def fail(*args):
        calls.append(args)
        raise ProviderError("provider_unavailable", retryable)

    monkeypatch.setattr("app.llm._post_json", fail)
    monkeypatch.setattr("app.llm.time.sleep", lambda _: None)
    with pytest.raises(ProviderError):
        request_json("chat", "https://example.test/api", "not-a-real-key", "test", {})
    assert len(calls) == expected
    with SessionLocal() as db:
        rows = list(db.scalars(select(Usage)))
        assert len(rows) == expected
        assert all(not row.success and row.cost is None for row in rows)


def test_invalid_usage_remains_unknown(monkeypatch):
    async def response(*args):
        return {"usage": {"prompt_tokens": "invalid", "completion_tokens": -1}}

    monkeypatch.setattr("app.llm._post_json", response)
    request_json("chat", "https://example.test/api", "not-a-real-key", "test", {})
    with SessionLocal() as db:
        usage = db.scalar(select(Usage))
        assert usage.input_tokens is None and usage.output_tokens is None and usage.cost is None


def test_global_quota_prevents_call(monkeypatch):
    monkeypatch.setattr(settings(), "daily_calls", 0)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        request_json("chat", "https://example.test/api", "unused", "test", {})
    assert exc.value.status_code == 429


def test_admin_login_rotation_and_document_controls(client):
    with SessionLocal.begin() as db:
        db.add(User(username="admin", password_hash=PasswordHasher().hash("test-password-long")))
    old_cookie = client.cookies.get("ashen_session")
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-password-long"})
    assert response.status_code == 200
    assert old_cookie != client.cookies.get("ashen_session")
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.get("/api/v1/admin/documents").status_code == 200
    data = {"project_id": "notes-of-ashen", "label": "v1"}
    assert (
        client.post("/api/v1/admin/documents", data=data, files={"files": ("bad.pdf", b"PDF")}).status_code
        == 422
    )
    assert (
        client.post("/api/v1/admin/documents", data=data, files={"files": ("bad.md", b"\xff")}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/admin/documents", data=data, files={"files": ("huge.md", b"a" * (2 * 1024 * 1024 + 1))}
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/v1/admin/documents", data=data, files={"files": ("good.md", b"# Supported\nTest document")}
        ).status_code
        == 202
    )


def test_builtin_errors_follow_contract(client):
    for method, path in [("get", "/api/v1/missing"), ("delete", "/api/v1/projects")]:
        response = getattr(client, method)(path)
        assert response.status_code in (404, 405)
        assert response.json()["error"]["request_id"]
