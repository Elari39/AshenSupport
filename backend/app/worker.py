import json
import logging
import threading
import time
from datetime import timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_, select

from app.config import settings
from app.db import Citation, Message, Run, Session, SessionLocal, Step, Task, event, now, uid
from app.knowledge import index_one
from app.llm import ProviderError, generate
from app.retrieval import retrieve
from app.schemas import Answer
from app.tools import execute_tool

log = logging.getLogger("ashen.worker")


class LostLease(Exception):
    pass


def claim():
    with SessionLocal.begin() as db:
        # Claims are serialized on task before run (same order as API cancellation).
        task = db.scalar(
            select(Task)
            .where(Task.status.in_(["queued", "running"]))
            .join(Run, Run.task_id == Task.id)
            .where(or_(Run.status == "queued", (Run.status == "running") & (Run.lease_until < now())))
            .order_by(Run.created_at)
            .with_for_update(skip_locked=True, of=Task)
            .limit(1)
        )
        if not task:
            return None
        run = db.scalar(
            select(Run)
            .where(Run.task_id == task.id, Run.status.in_(["queued", "running"]))
            .order_by(Run.created_at.desc())
            .with_for_update()
            .limit(1)
        )
        if run is None:
            return None
        if run.attempts >= 3:
            run.status, task.status, run.error, run.retryable = "failed", "failed", "recovery_limit", True
            event(db, task, "failed", message="执行恢复次数超过上限，可手动重试")
            return None
        run.owner, run.status, task.status = uid(), "running", "running"
        run.attempts += 1
        run.started_at = run.started_at or now()
        run.lease_until = now() + timedelta(seconds=settings().lease_seconds)
        event(db, task, "running", message="执行已开始", run_id=run.id, attempt=run.attempts)
        return run.id, run.owner, task.id


def locked_run(db, run_id, owner):
    run = db.get(Run, run_id)
    if run is None:
        raise LostLease()
    task = db.scalar(select(Task).where(Task.id == run.task_id).with_for_update())
    db.refresh(run, with_for_update=True)
    if (
        not task
        or task.status != "running"
        or run.status != "running"
        or run.owner != owner
        or run.lease_until < now()
    ):
        raise LostLease()
    return run, task


def heartbeat(run_id, owner, stopped):
    while not stopped.wait(max(1, settings().lease_seconds / 3)):
        try:
            with SessionLocal.begin() as db:
                run, _ = locked_run(db, run_id, owner)
                run.lease_until = now() + timedelta(seconds=settings().lease_seconds)
        except LostLease:
            return
        except Exception:
            log.warning(json.dumps({"run_id": run_id, "event": "heartbeat_failed"}))


def run_claim(claimed):
    run_id, owner, task_id = claimed
    started = time.monotonic()
    stopped = threading.Event()
    pulse = threading.Thread(target=heartbeat, args=(run_id, owner, stopped), daemon=True)
    pulse.start()

    def guard():
        if time.monotonic() - started > 180:
            raise ProviderError("execution_timeout", True)
        with SessionLocal() as db:
            run, task = db.get(Run, run_id), db.get(Task, task_id)
            if (
                not run
                or not task
                or run.owner != owner
                or run.status != "running"
                or task.status != "running"
            ):
                raise LostLease()
        return 180 - (time.monotonic() - started)

    def step(key, fn):
        guard()
        with SessionLocal() as db:
            saved = db.scalar(select(Step).where(Step.run_id == run_id, Step.key == key))
            if saved:
                return saved.result
        result = fn()
        guard()
        with SessionLocal.begin() as db:
            _, task = locked_run(db, run_id, owner)
            db.add(Step(run_id=run_id, key=key, result=result))
            event(
                db,
                task,
                "step",
                step=key,
                message=f"已完成：{key}",
                observation=result if key.startswith("tool") else None,
            )
        return result

    try:
        with SessionLocal() as db:
            task = db.get(Task, task_id)
            if task is None:
                raise LostLease()
            owner_session = db.get(Session, task.session_id)
            is_admin = bool(owner_session and owner_session.user_id)
            question = "\n".join(
                db.scalars(
                    select(Message.content)
                    .where(Message.task_id == task_id, Message.role == "user")
                    .order_by(Message.created_at)
                )
            )
            context: dict[str, Any] = {
                "question": question,
                "mode": task.mode,
                "scenario": task.scenario,
                "clarification_count": task.clarification_count,
                "observations": [],
                "project_id": task.project_id,
                "target_id": task.target_id,
            }
        retrieval = step(
            "retrieve", lambda: {"chunks": retrieve(context["project_id"], question, task_id, guard)}
        )
        context["chunks"] = retrieval["chunks"]
        references = {c["id"] for c in context["chunks"]}
        answer = None
        repair_used = False
        calls, tools = 0, 0
        while calls < 4:
            calls += 1
            raw = step(f"model:{calls}", lambda: generate(context, task_id, repair_used, guard))
            try:
                parsed = Answer.model_validate(raw)
                cited = set(parsed.citation_ids) | {
                    ref for cause in parsed.causes for ref in cause.citation_ids
                }
                if not cited <= references or (parsed.action == "tool" and not parsed.tool):
                    raise ValueError("invalid citation/tool")
            except (ValidationError, ValueError):
                if repair_used:
                    raise ProviderError("invalid_model_output") from None
                repair_used = True
                continue
            if parsed.action == "tool":
                if tools >= 3:
                    raise ProviderError("tool_limit")
                tools += 1
                observed = step(
                    f"tool:{tools}",
                    lambda: execute_tool(
                        parsed.tool, context["mode"], context["scenario"], context["target_id"], is_admin
                    ),
                )
                context["observations"].append(observed)
                continue
            answer = parsed
            break
        if answer is None:
            raise ProviderError("generation_limit")
        with SessionLocal.begin() as db:
            run, task = locked_run(db, run_id, owner)
            if answer.action == "clarify" and task.clarification_count >= 3:
                answer = Answer(
                    action="answer",
                    summary="补问已达上限，现有证据不足以判断原因。",
                    missing_information=answer.missing_information,
                )
            if answer.action == "clarify":
                task.clarification_count += 1
                task.status = "waiting_input"
            else:
                task.status = "completed"
            task.result = answer.model_dump()
            db.add(Message(task_id=task.id, role="assistant", content=answer.summary))
            for chunk in context["chunks"]:
                if chunk["id"] in (
                    set(answer.citation_ids) | {r for c in answer.causes for r in c.citation_ids}
                ):
                    db.add(Citation(task_id=task.id, chunk_id=chunk["id"], snapshot=chunk))
            run.status, run.finished_at = "completed", now()
            event(db, task, task.status, message=answer.summary, run_id=run.id)
    except LostLease:
        pass
    except Exception as exc:
        try:
            with SessionLocal.begin() as db:
                run, task = locked_run(db, run_id, owner)
                run.status, task.status = "failed", "failed"
                run.error = getattr(exc, "code", type(exc).__name__)
                run.retryable = getattr(exc, "retryable", False)
                run.finished_at = now()
                event(db, task, "failed", message=f"执行失败：{run.error}", run_id=run.id)
                log.error(json.dumps({"task_id": task_id, "run_id": run_id, "error": run.error}))
        except LostLease:
            pass
    finally:
        stopped.set()
        pulse.join(timeout=2)


def tick():
    claimed = claim()
    if claimed:
        run_claim(claimed)
        return True
    return index_one()


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    last_cleanup = 0.0
    while True:
        try:
            if time.monotonic() - last_cleanup > 3600:
                from app.cli import cleanup

                cleanup()
                last_cleanup = time.monotonic()
            if not tick():
                time.sleep(0.5)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            log.error(json.dumps({"event": "worker_error", "type": type(exc).__name__}))
            time.sleep(2)


if __name__ == "__main__":
    main()
