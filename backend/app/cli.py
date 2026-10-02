import argparse
import getpass
import json
from pathlib import Path

from argon2 import PasswordHasher
from sqlalchemy import delete, select

from app.db import (
    Approval,
    Citation,
    Draft,
    Event,
    Message,
    Project,
    Quota,
    Run,
    Session,
    SessionLocal,
    Step,
    Task,
    Ticket,
    User,
    now,
)
from app.knowledge import import_document


def seed():
    root = Path(__file__).resolve().parents[2] / "fixtures" / "docs"
    if not root.exists():
        root = Path("/fixtures/docs")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    with SessionLocal.begin() as db:
        for project_id, name in [("notes-of-ashen", "Notes of Ashen"), ("ashen-courier", "AshenCourier")]:
            if not db.get(Project, project_id):
                db.add(Project(id=project_id, name=name, description="开源项目技术支持"))
                db.flush()
            for path in (root / project_id).glob("*.md"):
                provenance = next(
                    (
                        item
                        for item in manifest
                        if item["project"] == project_id and item["file"] == path.name
                    ),
                    None,
                )
                source = (
                    f"{provenance['source_repo']}/blob/{provenance['commit']}/{path.name}"
                    if provenance and not provenance["working_tree_modified"]
                    else ""
                )
                import_document(
                    db,
                    project_id,
                    path.name,
                    path.read_text(encoding="utf-8"),
                    provenance["commit"][:12] if provenance else "fixture-v1",
                    source,
                )


def cleanup():
    with SessionLocal.begin() as db:
        # Expired guest sessions only. Admin data is never subject to guest retention.
        ids = list(
            db.scalars(select(Session.id).where(Session.user_id.is_(None), Session.expires_at < now()))
        )
        if ids:
            task_ids = list(db.scalars(select(Task.id).where(Task.session_id.in_(ids))))
            run_ids = select(Run.id).where(Run.task_id.in_(task_ids))
            draft_ids = select(Draft.id).where(Draft.task_id.in_(task_ids))
            db.execute(delete(Approval).where(Approval.draft_id.in_(draft_ids)))
            db.execute(delete(Ticket).where(Ticket.task_id.in_(task_ids)))
            db.execute(delete(Draft).where(Draft.task_id.in_(task_ids)))
            db.execute(delete(Step).where(Step.run_id.in_(run_ids)))
            db.execute(delete(Run).where(Run.task_id.in_(task_ids)))
            db.execute(delete(Citation).where(Citation.task_id.in_(task_ids)))
            db.execute(delete(Event).where(Event.task_id.in_(task_ids)))
            db.execute(delete(Message).where(Message.task_id.in_(task_ids)))
            db.execute(delete(Task).where(Task.id.in_(task_ids)))
            db.execute(delete(Session).where(Session.id.in_(ids)))
        db.execute(delete(Quota).where(Quota.key < str(now().date())))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed", "admin", "cleanup"])
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    if args.command == "seed":
        seed()
    elif args.command == "cleanup":
        cleanup()
    else:
        password = getpass.getpass("New administrator password (12+ characters): ")
        if len(password) < 12:
            raise SystemExit("Password must contain at least 12 characters")
        with SessionLocal.begin() as db:
            user = db.scalar(select(User).where(User.username == args.username))
            if not user:
                user = User(username=args.username, password_hash="")
                db.add(user)
                db.flush()
            user.password_hash = PasswordHasher().hash(password)
            for session in db.scalars(select(Session).where(Session.user_id == user.id)):
                session.expires_at = now()
        print("Administrator saved; previous sessions revoked.")


if __name__ == "__main__":
    main()
