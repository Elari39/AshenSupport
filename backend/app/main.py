import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.db import (
    Approval,
    Citation,
    Document,
    DocumentVersion,
    Draft,
    Event,
    Message,
    Project,
    Run,
    Session,
    SessionLocal,
    Task,
    Ticket,
    Usage,
    User,
    event,
    now,
    uid,
)
from app.schemas import DecisionInput, DraftInput, Login, MessageInput, TaskInput, TicketInput
from app.security import consume, create_session, digest, fail, identity, origin_check

log = logging.getLogger("ashen")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app):
    yield


app = FastAPI(title="AshenSupport", version="0.1.0", lifespan=lifespan)


def serial(obj):
    return {
        column.name: (
            getattr(obj, column.name).isoformat() + "Z"
            if isinstance(getattr(obj, column.name), datetime)
            else getattr(obj, column.name)
        )
        for column in obj.__table__.columns
    }


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = uid()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = (
        exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    )
    headers = {"Retry-After": "3600"} if exc.status_code == 429 else {}
    return JSONResponse(
        {"error": {**detail, "request_id": request.state.request_id, "details": None}},
        status_code=exc.status_code,
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc):
    return await http_error(
        request, HTTPException(422, {"code": "invalid_input", "message": "输入格式不正确"})
    )


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc):
    return await http_error(
        request, HTTPException(409, {"code": "conflict", "message": "状态已变化，请刷新"})
    )


@app.exception_handler(Exception)
async def unexpected(request: Request, exc):
    log.error(json.dumps({"request_id": request.state.request_id, "error_type": type(exc).__name__}))
    return await http_error(
        request, HTTPException(500, {"code": "internal_error", "message": "服务暂时不可用"})
    )


def get_task(db, task_id, session, lock=False):
    stmt = select(Task).where(Task.id == task_id)
    if not session.user_id:
        stmt = stmt.where(Task.session_id == session.id)
    task = db.scalar(stmt.with_for_update() if lock else stmt)
    if task is None:
        fail(404, "not_found", "任务不存在")
    return task


def require_state(task, *states):
    if task.status not in states:
        fail(409, "invalid_state", "任务状态已变化，请刷新")


def enqueue(db, task):
    task.status = "queued"
    db.add(Run(task_id=task.id))
    event(db, task, "queued", message="任务已进入队列")


@app.get("/healthz")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/v1/sessions/guest")
def guest(request: Request, response: Response):
    origin_check(request)
    with SessionLocal.begin() as db:
        existing = db.scalar(
            select(Session).where(
                Session.token_hash == digest(request.cookies.get("ashen_session", "")),
                Session.expires_at > now(),
            )
        )
        if existing:
            return {"role": "admin" if existing.user_id else "guest", "csrf_token": existing.csrf}
        consume(db, f"sessions:{digest(request.client.host if request.client else 'unknown')}", 20)
        session = create_session(db, response)
        return {"role": "guest", "csrf_token": session.csrf}


@app.get("/api/v1/me")
def me(request: Request):
    with SessionLocal() as db:
        session = identity(request, db)
        return {
            "role": "admin" if session.user_id else "guest",
            "csrf_token": session.csrf,
            "provider": settings().provider,
            "health_targets": list(settings().health_targets) if session.user_id else [],
            "retention_days": 7,
        }


@app.post("/api/v1/auth/login")
def login(body: Login, request: Request, response: Response):
    # Persist the failed-login budget as well as successful attempts.
    with SessionLocal.begin() as db:
        identity(request, db, write=True)
        consume(db, f"login:{digest(request.client.host if request.client else 'unknown')}", 30)
    with SessionLocal.begin() as db:
        old = identity(request, db, write=True)
        user = db.scalar(select(User).where(User.username == body.username))
        try:
            PasswordHasher().verify(user.password_hash if user else DUMMY_HASH, body.password)
        except VerificationError:
            fail(401, "invalid_credentials", "账号或密码不正确")
        if user is None:
            fail(401, "invalid_credentials", "账号或密码不正确")
        old.expires_at = now()
        session = create_session(db, response, user.id)
        return {"role": "admin", "csrf_token": session.csrf}


DUMMY_HASH = PasswordHasher().hash(uid())


@app.post("/api/v1/auth/logout")
def logout(request: Request, response: Response):
    with SessionLocal.begin() as db:
        identity(request, db, write=True).expires_at = now()
    response.delete_cookie("ashen_session")
    return {"ok": True}


@app.get("/api/v1/projects")
def projects(request: Request):
    with SessionLocal() as db:
        identity(request, db)
        return [serial(row) for row in db.scalars(select(Project).order_by(Project.id))]


@app.post("/api/v1/tasks", status_code=202)
def new_task(body: TaskInput, request: Request):
    with SessionLocal.begin() as db:
        session = identity(request, db, write=True)
        # Serialize per-session task creation; queued tasks count against concurrency too.
        db.scalar(select(Session).where(Session.id == session.id).with_for_update())
        if not db.get(Project, body.project_id):
            fail(404, "not_found", "项目不存在")
        if body.mode == "live" and (not session.user_id or body.target_id not in settings().health_targets):
            fail(403, "tool_forbidden", "没有可用的真实诊断目标")
        if not session.user_id:
            if db.scalar(
                select(Task.id).where(Task.session_id == session.id, Task.status.in_(["queued", "running"]))
            ):
                fail(409, "active_task", "请等待当前任务完成")
            consume(db, f"session:{session.id}", settings().session_tasks)
            consume(
                db, f"ip:{digest(request.client.host if request.client else 'unknown')}", settings().ip_tasks
            )
        task = Task(
            session_id=session.id,
            project_id=body.project_id,
            title=body.message[:100],
            mode=body.mode,
            scenario=body.scenario,
            target_id=body.target_id,
        )
        db.add(task)
        db.flush()
        db.add(Message(task_id=task.id, role="user", content=body.message))
        enqueue(db, task)
        return {"id": task.id, "status": task.status}


@app.get("/api/v1/tasks")
def task_list(
    request: Request, project_id: str | None = None, status: str | None = None, cursor: str | None = None
):
    with SessionLocal() as db:
        session = identity(request, db)
        stmt = select(Task)
        if not session.user_id:
            stmt = stmt.where(Task.session_id == session.id)
        if project_id:
            stmt = stmt.where(Task.project_id == project_id)
        if status:
            stmt = stmt.where(Task.status == status)
        if cursor:
            try:
                stamp, last_id = cursor.split("|", 1)
                stamp_dt = datetime.fromisoformat(stamp)
            except ValueError:
                fail(422, "invalid_cursor", "分页游标无效")
            stmt = stmt.where(
                (Task.created_at < stamp_dt) | ((Task.created_at == stamp_dt) & (Task.id < last_id))
            )
        rows = list(db.scalars(stmt.order_by(Task.created_at.desc(), Task.id.desc()).limit(21)))
        visible = rows[:20]
        next_cursor = f"{visible[-1].created_at.isoformat()}|{visible[-1].id}" if len(rows) > 20 else None
        return {"items": [serial(row) for row in visible], "next_cursor": next_cursor}


@app.get("/api/v1/tasks/{task_id}")
def task_detail(task_id: str, request: Request):
    with SessionLocal() as db:
        task = get_task(db, task_id, identity(request, db))
        return {
            **serial(task),
            "messages": [
                serial(m)
                for m in db.scalars(
                    select(Message).where(Message.task_id == task_id).order_by(Message.created_at, Message.id)
                )
            ],
            "events": [
                serial(e)
                for e in db.scalars(select(Event).where(Event.task_id == task_id).order_by(Event.id))
            ],
            "citations": [
                c.snapshot for c in db.scalars(select(Citation).where(Citation.task_id == task_id))
            ],
            "draft": (serial(d) if (d := db.scalar(select(Draft).where(Draft.task_id == task_id))) else None),
            "runs": [
                serial(r)
                for r in db.scalars(select(Run).where(Run.task_id == task_id).order_by(Run.created_at))
            ],
        }


@app.post("/api/v1/tasks/{task_id}/messages", status_code=202)
def add_message(task_id: str, body: MessageInput, request: Request):
    with SessionLocal.begin() as db:
        session = identity(request, db, write=True)
        db.scalar(select(Session).where(Session.id == session.id).with_for_update())
        task = get_task(db, task_id, session, lock=True)
        require_state(task, "waiting_input")
        ensure_no_other_active(db, task, session)
        db.add(Message(task_id=task.id, role="user", content=body.message))
        enqueue(db, task)
        return {"id": task.id, "status": task.status}


def ensure_no_other_active(db, task, session):
    if not session.user_id and db.scalar(
        select(Task.id).where(
            Task.session_id == session.id, Task.id != task.id, Task.status.in_(["queued", "running"])
        )
    ):
        fail(409, "active_task", "已有其他任务正在执行")


@app.post("/api/v1/tasks/{task_id}/cancel")
def cancel(task_id: str, request: Request):
    with SessionLocal.begin() as db:
        task = get_task(db, task_id, identity(request, db, write=True), lock=True)
        require_state(task, "queued", "running", "waiting_input", "waiting_approval")
        task.status = "cancelled"
        for run in db.scalars(
            select(Run).where(Run.task_id == task.id, Run.status.in_(["queued", "running"]))
        ):
            run.status = "cancelled"
            run.owner = None
        draft = db.scalar(select(Draft).where(Draft.task_id == task.id))
        if draft and draft.status == "pending":
            draft.status = "cancelled"
        event(db, task, "cancelled", message="用户已取消")
        return {"id": task.id, "status": task.status}


@app.post("/api/v1/tasks/{task_id}/retry", status_code=202)
def retry(task_id: str, request: Request):
    with SessionLocal.begin() as db:
        session = identity(request, db, write=True)
        db.scalar(select(Session).where(Session.id == session.id).with_for_update())
        task = get_task(db, task_id, session, lock=True)
        require_state(task, "failed")
        ensure_no_other_active(db, task, session)
        previous = db.scalar(
            select(Run).where(Run.task_id == task.id).order_by(Run.created_at.desc()).limit(1)
        )
        if not previous or not previous.retryable:
            fail(409, "not_retryable", "此错误不能自动重试，请检查配置")
        enqueue(db, task)
        return {"id": task.id, "status": task.status}


@app.get("/api/v1/tasks/{task_id}/events")
def events(task_id: str, request: Request, after: int = 0):
    with SessionLocal() as db:
        get_task(db, task_id, identity(request, db))
    try:
        start = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        fail(422, "invalid_cursor", "事件游标无效")

    async def stream():
        cursor = start
        while not await request.is_disconnected():
            with SessionLocal() as db:
                try:
                    task = get_task(db, task_id, identity(request, db))
                except HTTPException:
                    return
                rows = list(
                    db.scalars(
                        select(Event)
                        .where(Event.task_id == task_id, Event.id > cursor)
                        .order_by(Event.id)
                        .limit(100)
                    )
                )
                terminal = task.status not in ["queued", "running"]
                for row in rows:
                    cursor = row.id
                    yield f"id: {row.id}\ndata: {json.dumps(serial(row), ensure_ascii=False)}\n\n"
                if terminal and len(rows) < 100:
                    yield "event: done\ndata: {}\n\n"
                    return
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@app.post("/api/v1/tasks/{task_id}/ticket-draft")
def make_draft(task_id: str, request: Request):
    with SessionLocal.begin() as db:
        task = get_task(db, task_id, identity(request, db, write=True), lock=True)
        existing = db.scalar(select(Draft).where(Draft.task_id == task_id))
        if existing:
            return serial(existing)
        require_state(task, "completed")
        draft = Draft(
            task_id=task.id,
            title=task.title,
            description=(task.result or {}).get("summary", task.title),
            evidence={
                "result": task.result,
                "citations": [
                    c.snapshot for c in db.scalars(select(Citation).where(Citation.task_id == task.id))
                ],
            },
        )
        db.add(draft)
        db.flush()
        task.status = "waiting_approval"
        event(db, task, "waiting_approval", message="工单草稿等待人工审批")
        return serial(draft)


def owned_draft(db, draft_id, session):
    # Lock task first everywhere to keep the cancellation/approval lock order consistent.
    draft = db.get(Draft, draft_id)
    if draft is None:
        fail(404, "not_found", "草稿不存在")
    task = get_task(db, draft.task_id, session, lock=True)
    db.refresh(draft, with_for_update=True)
    return draft, task


@app.patch("/api/v1/ticket-drafts/{draft_id}")
def edit_draft(draft_id: str, body: DraftInput, request: Request):
    with SessionLocal.begin() as db:
        draft, task = owned_draft(db, draft_id, identity(request, db, write=True))
        require_state(task, "waiting_approval")
        if draft.version != body.version or draft.status != "pending":
            fail(409, "stale_draft", "草稿已变化")
        draft.title, draft.description = body.title, body.description
        draft.version += 1
        event(db, task, "draft_updated", draft_version=draft.version)
        return serial(draft)


@app.post("/api/v1/ticket-drafts/{draft_id}/decision")
def decide(draft_id: str, body: DecisionInput, request: Request):
    with SessionLocal.begin() as db:
        session = identity(request, db, write=True)
        draft, task = owned_draft(db, draft_id, session)
        if draft.version != body.version:
            fail(409, "stale_draft", "请重新审核最新版本")
        previous = db.scalar(
            select(Approval).where(Approval.draft_id == draft.id, Approval.version == body.version)
        )
        if previous:
            if previous.decision != body.decision:
                fail(409, "already_decided", "草稿已有不同审批决定")
            ticket = db.scalar(select(Ticket).where(Ticket.draft_id == draft.id))
            return {"decision": previous.decision, "ticket_id": ticket.id if ticket else None}
        require_state(task, "waiting_approval")
        if draft.status != "pending":
            fail(409, "already_decided", "草稿不可审批")
        db.add(
            Approval(
                draft_id=draft.id,
                version=draft.version,
                decision=body.decision,
                session_id=session.id,
                idempotency_key=body.idempotency_key,
            )
        )
        ticket = None
        if body.decision == "approve":
            ticket = Ticket(
                draft_id=draft.id,
                task_id=task.id,
                session_id=task.session_id,
                project_id=task.project_id,
                title=draft.title,
                description=draft.description,
                evidence=draft.evidence,
                sandbox=task.mode == "sandbox",
            )
            db.add(ticket)
            db.flush()
        draft.status = body.decision
        task.status = "completed"
        event(db, task, "approval", decision=body.decision, ticket_id=ticket.id if ticket else None)
        return {"decision": body.decision, "ticket_id": ticket.id if ticket else None}


@app.get("/api/v1/tickets")
def tickets(request: Request, sandbox: bool = False):
    with SessionLocal() as db:
        session = identity(request, db)
        stmt = select(Ticket)
        stmt = (
            stmt.where(Ticket.sandbox == sandbox)
            if session.user_id
            else stmt.where(Ticket.session_id == session.id)
        )
        return [serial(t) for t in db.scalars(stmt.order_by(Ticket.created_at.desc()).limit(100))]


def owned_ticket(db, ticket_id, session):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or (not session.user_id and ticket.session_id != session.id):
        fail(404, "not_found", "工单不存在")
    return ticket


@app.get("/api/v1/tickets/{ticket_id}")
def ticket_detail(ticket_id: str, request: Request):
    with SessionLocal() as db:
        ticket = owned_ticket(db, ticket_id, identity(request, db))
        return {
            **serial(ticket),
            "approvals": [
                serial(a) for a in db.scalars(select(Approval).where(Approval.draft_id == ticket.draft_id))
            ],
        }


@app.patch("/api/v1/tickets/{ticket_id}")
def close_ticket(ticket_id: str, body: TicketInput, request: Request):
    with SessionLocal.begin() as db:
        ticket = owned_ticket(db, ticket_id, identity(request, db, write=True))
        ticket.status = body.status
        return serial(ticket)


@app.get("/api/v1/admin/documents")
def documents(request: Request):
    with SessionLocal() as db:
        identity(request, db, admin=True)
        return [
            {
                **serial(d),
                "versions": [
                    serial(v) | {"content": None}
                    for v in db.scalars(
                        select(DocumentVersion)
                        .where(DocumentVersion.document_id == d.id)
                        .order_by(DocumentVersion.created_at.desc())
                    )
                ],
            }
            for d in db.scalars(select(Document).order_by(Document.logical_key))
        ]


@app.get("/api/v1/admin/documents/{document_id}/chunks")
def document_chunks(document_id: str, request: Request):
    from app.db import Chunk

    with SessionLocal() as db:
        identity(request, db, admin=True)
        document = db.get(Document, document_id)
        if not document:
            fail(404, "not_found", "文档不存在")
        return [
            {k: v for k, v in serial(c).items() if k != "vector"}
            for c in db.scalars(select(Chunk).where(Chunk.version_id == document.active_version))
        ]


@app.post("/api/v1/admin/documents", status_code=202)
def import_documents(
    request: Request,
    files: list[UploadFile] = File(),
    project_id: str = Form(),
    label: str = Form("v1"),
    source: str = Form(""),
):
    from app.knowledge import import_document

    with SessionLocal.begin() as db:
        identity(request, db, write=True, admin=True)
        if len(files) > 20 or not files or len(label) > 200 or len(source) > 2000:
            fail(422, "invalid_import", "每次最多 20 个文件，版本和来源长度须符合限制")
        if not db.get(Project, project_id):
            fail(404, "not_found", "项目不存在")
        rows = []
        for file in files:
            name = file.filename or ""
            if not name.lower().endswith((".md", ".txt")) or len(name) > 200:
                fail(422, "invalid_file", "仅支持 Markdown/TXT")
            content = file.file.read(2 * 1024 * 1024 + 1)
            if len(content) > 2 * 1024 * 1024:
                fail(413, "file_too_large", "单文件不能超过 2 MiB")
            try:
                decoded = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                fail(422, "invalid_encoding", "文件必须是 UTF-8")
            rows.append(import_document(db, project_id, name, decoded, label, source))
        return [{"id": row.id, "status": row.status} for row in rows]


@app.post("/api/v1/admin/documents/{document_id}/reindex", status_code=202)
def reindex(document_id: str, request: Request):
    from app.knowledge import import_document

    with SessionLocal.begin() as db:
        identity(request, db, write=True, admin=True)
        document = db.get(Document, document_id)
        if document is None:
            fail(404, "not_found", "文档不存在")
        version = db.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.created_at.desc())
            .limit(1)
        )
        if version is None:
            fail(409, "no_version", "文档没有可重建版本")
        row = import_document(
            db, document.project_id, document.logical_key, version.content, version.label, version.source
        )
        if row.status == "failed":
            row.status, row.error = "queued", None
        return {"id": row.id, "status": row.status}


@app.delete("/api/v1/admin/documents/{document_id}")
def disable_document(document_id: str, request: Request):
    with SessionLocal.begin() as db:
        identity(request, db, write=True, admin=True)
        document = db.get(Document, document_id)
        if not document:
            fail(404, "not_found", "文档不存在")
        document.enabled = False
        return {"ok": True}


@app.get("/api/v1/admin/usage")
def usage(request: Request):
    with SessionLocal() as db:
        identity(request, db, admin=True)
        rows = list(db.scalars(select(Usage).order_by(Usage.created_at.desc()).limit(2000)))
        runs = list(db.scalars(select(Run).order_by(Run.created_at.desc()).limit(500)))
        return {
            "items": [serial(row) for row in rows],
            "runs": [serial(row) for row in runs],
            "provider": settings().provider,
        }
