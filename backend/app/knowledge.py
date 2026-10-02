import hashlib
import re

from sqlalchemy import select

from app.config import settings
from app.db import Chunk, Document, DocumentVersion, SessionLocal
from app.llm import embed, embedding_id
from app.security import fail


def split_document(content, target=800, overlap=120):
    """Keep exact source line coordinates, including long single-line paragraphs."""
    lines = content.splitlines(keepends=True)
    headings: list[str] = []
    buffer = ""
    start = 1
    chunks = []
    for number, line in enumerate(lines, 1):
        heading = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading and buffer.strip():
            chunks.append(
                {
                    "content": buffer.strip(),
                    "heading": " / ".join(headings),
                    "line_start": start,
                    "line_end": number - 1,
                }
            )
            buffer, start = "", number
        if heading:
            depth = len(heading[1])
            headings = headings[: depth - 1] + [heading[2].strip()]
        if not buffer:
            start = number
        buffer += line
        while len(buffer) > target:
            piece = buffer[:target]
            chunks.append(
                {
                    "content": piece,
                    "heading": " / ".join(headings),
                    "line_start": start,
                    "line_end": start + piece.count("\n"),
                }
            )
            removed = buffer[: target - overlap]
            start += removed.count("\n")
            buffer = buffer[target - overlap :]
        if not line.strip() and len(buffer) > target // 2:
            chunks.append(
                {
                    "content": buffer.strip(),
                    "heading": " / ".join(headings),
                    "line_start": start,
                    "line_end": number,
                }
            )
            buffer = ""
    if buffer.strip():
        chunks.append(
            {
                "content": buffer.strip(),
                "heading": " / ".join(headings),
                "line_start": start,
                "line_end": max(1, len(lines)),
            }
        )
    return chunks


def import_document(db, project_id, key, content, label, source):
    if not content.strip() or "\x00" in content:
        fail(422, "invalid_document", "文档为空或包含无效字符")
    document = db.scalar(
        select(Document)
        .where(Document.project_id == project_id, Document.logical_key == key)
        .with_for_update()
    )
    if not document:
        document = Document(project_id=project_id, logical_key=key)
        db.add(document)
        db.flush()
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    existing = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.content_hash == content_hash,
            DocumentVersion.embedding_id == embedding_id(),
        )
    )
    if existing:
        if existing.status == "ready":
            document.active_version, document.enabled = existing.id, True
        return existing
    version = DocumentVersion(
        document_id=document.id,
        content=content,
        label=label,
        source=source,
        content_hash=content_hash,
        embedding_id=embedding_id(),
        config={"target": 800, "overlap": 120, "dimensions": settings().embedding_dimensions},
    )
    db.add(version)
    db.flush()
    return version


def index_one():
    # Holding one version row lock lets another worker index a different version safely.
    # Embedding budget/usage uses separate short transactions; document rows are not locked during network I/O.
    with SessionLocal.begin() as db:
        version = db.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.status == "queued")
            .order_by(DocumentVersion.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not version:
            return False
        try:
            if version.embedding_id != embedding_id():
                raise ValueError("embedding_configuration_changed")
            chunks = split_document(version.content)
            vectors = []
            for start in range(0, len(chunks), 32):
                vectors.extend(embed([c["content"] for c in chunks[start : start + 32]]))
            for chunk, vector in zip(chunks, vectors, strict=True):
                db.add(Chunk(version_id=version.id, vector=vector, **chunk))
            document = db.scalar(select(Document).where(Document.id == version.document_id).with_for_update())
            assert document is not None
            version.status = "ready"
            version.error = None
            # Older index completion must not replace a newer active version.
            active = db.get(DocumentVersion, document.active_version) if document.active_version else None
            if not active or active.created_at <= version.created_at:
                document.active_version = version.id
        except Exception as exc:
            version.status, version.error = "failed", getattr(exc, "code", type(exc).__name__)
    return True
