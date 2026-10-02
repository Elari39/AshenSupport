import hashlib
import secrets
from datetime import timedelta
from typing import NoReturn

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.config import settings
from app.db import Quota, Session, now


def fail(status: int, code: str, message: str) -> NoReturn:
    raise HTTPException(status, {"code": code, "message": message})


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def origin_check(request: Request):
    if request.headers.get("origin") != settings().origin:
        fail(403, "origin_rejected", "请求来源不被允许")


def identity(request: Request, db, write=False, admin=False):
    token = request.cookies.get("ashen_session", "")
    session = db.scalar(
        select(Session).where(Session.token_hash == digest(token), Session.expires_at > now())
    )
    if session is None:
        fail(401, "unauthenticated", "请先建立访客会话或登录")
    if write:
        origin_check(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            fail(403, "csrf_rejected", "页面已过期，请刷新后重试")
    if admin and session.user_id is None:
        fail(403, "forbidden", "此操作仅供管理员使用")
    return session


def create_session(db, response, user_id=None):
    token = secrets.token_urlsafe(32)
    session = Session(
        token_hash=digest(token),
        csrf=secrets.token_urlsafe(32),
        user_id=user_id,
        expires_at=now() + timedelta(days=7),
    )
    db.add(session)
    db.flush()
    response.set_cookie(
        "ashen_session",
        token,
        httponly=True,
        secure=settings().secure_cookie,
        samesite="lax",
        max_age=7 * 86400,
        path="/",
    )
    return session


def consume(db, key: str, limit: int):
    """Atomic counters in the caller's transaction. Never SELECT then INSERT."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    key = f"{now().date()}:{key}"
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(Quota).values(key=key, count=1)
    returning = stmt.on_conflict_do_update(
        index_elements=[Quota.key], set_={"count": Quota.count + 1}, where=Quota.count < limit
    ).returning(Quota.count)
    if limit < 1 or db.scalar(returning) is None:
        fail(429, "quota_exceeded", "今日额度已用完；共享网络也可能达到 IP 限额")
