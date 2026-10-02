import math
from functools import lru_cache

from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.config import settings
from app.db import Chunk, Document, DocumentVersion, SessionLocal
from app.llm import ProviderError, embed, embedding_id, request_json, terms


@lru_cache(maxsize=16)
def lexical_index(snapshot):
    return BM25Okapi([terms(content) or ["_"] for _, content in snapshot])


def retrieve(project_id, question, task_id=None, guard=None, mode=None):
    cfg = settings()
    mode = mode or cfg.retrieval_mode
    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(Chunk, DocumentVersion, Document)
                .join(DocumentVersion, Chunk.version_id == DocumentVersion.id)
                .join(Document, Document.active_version == DocumentVersion.id)
                .where(
                    Document.project_id == project_id,
                    Document.enabled.is_(True),
                    DocumentVersion.embedding_id == embedding_id(),
                )
            ).all()
        )
        chunks = [
            {
                "id": c.id,
                "content": c.content,
                "heading": c.heading,
                "line_start": c.line_start,
                "line_end": c.line_end,
                "document": d.logical_key,
                "version": v.label,
                "version_id": v.id,
                "source": v.source,
                "vector": list(c.vector),
            }
            for c, v, d in rows
        ]
    if not chunks:
        return []
    vector = embed([question], task_id, guard)[0]

    def cosine(chunk):
        candidate = chunk["vector"]
        denom = math.sqrt(sum(v * v for v in vector) * sum(v * v for v in candidate)) or 1
        return sum(a * b for a, b in zip(vector, candidate, strict=True)) / denom

    dense = sorted(range(len(chunks)), key=lambda i: cosine(chunks[i]), reverse=True)[:20]
    ranked = dense
    if mode in ["hybrid", "rerank"]:
        snapshot = tuple((c["id"], c["content"]) for c in chunks)
        scores = lexical_index(snapshot).get_scores(terms(question))
        sparse = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:20]
        fused: dict[int, float] = {}
        for sequence in (dense, sparse):
            for rank, i in enumerate(sequence):
                fused[i] = fused.get(i, 0) + 1 / (61 + rank)
        ranked = sorted(fused, key=lambda i: fused[i], reverse=True)[:10]
    if mode == "rerank":
        if not cfg.rerank_url:
            raise ProviderError("rerank_not_configured")
        result = request_json(
            "rerank",
            cfg.rerank_url,
            cfg.rerank_key,
            cfg.rerank_model,
            {
                "model": cfg.rerank_model,
                "query": question,
                "documents": [chunks[i]["content"] for i in ranked],
                "top_n": 6,
            },
            task_id,
            guard,
        )
        try:
            indices = [row["index"] for row in result["results"]]
            if len(indices) != len(set(indices)) or any(
                type(i) is not int or not 0 <= i < len(ranked) for i in indices
            ):
                raise ValueError("index")
            ranked = [ranked[i] for i in indices]
        except (ValueError, KeyError, TypeError):
            raise ProviderError("rerank_contract_invalid") from None
    return [{key: value for key, value in chunks[i].items() if key != "vector"} for i in ranked[:6]]
