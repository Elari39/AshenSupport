import socket

import pytest
from sqlalchemy import select

from app.db import Document, DocumentVersion, SessionLocal
from app.knowledge import import_document, index_one, split_document
from app.llm import ProviderError
from app.retrieval import retrieve
from app.tools import execute_tool, public_addresses


def test_index_versions_and_failure_preserve_active(monkeypatch):
    with SessionLocal.begin() as db:
        first = import_document(db, "notes-of-ashen", "a.md", "# First\nRAG Qdrant 索引", "v1", "")
        first_id = first.id
    assert index_one()
    with SessionLocal.begin() as db:
        same = import_document(db, "notes-of-ashen", "a.md", "# First\nRAG Qdrant 索引", "v1", "")
        assert same.id == first_id
        second = import_document(db, "notes-of-ashen", "a.md", "# New\nNew content", "v2", "")
        second_id = second.id
    monkeypatch.setattr("app.knowledge.embed", lambda *a: (_ for _ in ()).throw(ProviderError("bad_key")))
    assert index_one()
    with SessionLocal() as db:
        assert db.get(DocumentVersion, second_id).status == "failed"
        assert db.scalar(select(Document)).active_version == first_id
    assert retrieve("notes-of-ashen", "RAG 索引")
    assert retrieve("ashen-courier", "RAG 索引") == []


def test_line_coordinates_and_long_paragraph():
    content = "# 标题\n\n" + "长文" * 1000
    chunks = split_document(content)
    assert len(chunks) > 2
    assert all(len(c["content"]) <= 800 for c in chunks)
    assert all(1 <= c["line_start"] <= c["line_end"] <= 3 for c in chunks)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"])
def test_private_addresses_blocked(monkeypatch, address):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    )
    with pytest.raises(ProviderError, match="forbidden"):
        public_addresses("example.test", 443)


def test_tool_permission_cannot_be_overridden():
    with pytest.raises(ProviderError, match="forbidden"):
        execute_tool("read_health", "sandbox", "rag", "target", False)
    with pytest.raises(ProviderError, match="forbidden"):
        execute_tool("shell", "live", "rag", "target", True)
    assert execute_tool("simulate_health", "sandbox", "rag", None, False)["simulated"]
