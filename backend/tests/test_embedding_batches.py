import pytest

from app.config import settings
from app.llm import ProviderError, embed


def test_large_embedding_input_is_split_without_relaxing_indices(monkeypatch):
    monkeypatch.setattr(settings(), "provider", "online")
    monkeypatch.setattr(settings(), "embedding_dimensions", 8)
    monkeypatch.setattr(settings(), "embedding_batch_size", 8)
    batches = []

    def request(kind, url, key, model, payload, *args):
        batch = payload["input"]
        batches.append(batch)
        return {"data": [{"index": i, "embedding": [float(value)] * 8} for i, value in enumerate(batch)]}

    monkeypatch.setattr("app.llm.request_json", request)
    vectors = embed([str(i) for i in range(19)])
    assert [len(batch) for batch in batches] == [8, 8, 3]
    assert [v[0] for v in vectors] == list(range(19))


def test_duplicate_indices_are_still_rejected(monkeypatch):
    monkeypatch.setattr(settings(), "provider", "online")
    monkeypatch.setattr(settings(), "embedding_dimensions", 8)
    monkeypatch.setattr("app.llm.request_json", lambda *a: {"data": [
        {"index": 0, "embedding": [0.] * 8}, {"index": 0, "embedding": [1.] * 8}]})
    with pytest.raises(ProviderError, match="embedding_contract_invalid"):
        embed(["first", "second"])
