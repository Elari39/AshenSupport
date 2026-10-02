"""Small, explicit paid connectivity probe. Never logs endpoints or credentials."""
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


async def main():
    config = dotenv_values(ROOT / ".env", encoding="utf-8-sig")
    chat_url = config["ASHEN_CHAT_URL"].rstrip("/")
    if not urlsplit(chat_url).path:
        chat_url += "/v1/chat/completions"
    elif urlsplit(chat_url).path.rstrip("/") == "/v1":
        chat_url += "/chat/completions"
    jobs = [
        ("chat", chat_url, config["ASHEN_CHAT_KEY"], {
            "model": config["ASHEN_CHAT_MODEL"], "max_tokens": 256, "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": 'Return only JSON: {"status":"ok"}'}],
        }),
        ("embedding", config["ASHEN_EMBEDDING_URL"], config["ASHEN_EMBEDDING_KEY"], {
            "model": config["ASHEN_EMBEDDING_MODEL"], "input": ["RAG 问答依赖向量索引。", "如何检查 Qdrant 索引？"],
        }),
    ]
    async def probe(kind, url, key, payload):
        start = time.perf_counter()
        record = {"kind": kind, "model": payload["model"]}
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False) as client:
                response = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload)
            record["http_status"] = response.status_code
            if response.status_code == 200:
                data = response.json()
                record["usage"] = data.get("usage")
                if kind == "embedding":
                    record["dimensions"] = [len(row["embedding"]) for row in data["data"]]
                else:
                    record["content"] = data["choices"][0]["message"].get("content")
                    record["finish_reason"] = data["choices"][0].get("finish_reason")
            else:
                try:
                    error = response.json().get("error", {})
                    record["error_code"] = error.get("code") if isinstance(error, dict) else "provider_error"
                except ValueError:
                    record["error_code"] = "non_json_error"
        except Exception as exc:
            record["error_type"] = type(exc).__name__
        record["elapsed_ms"] = round((time.perf_counter() - start) * 1000)
        return record
    results = await asyncio.gather(*(probe(*job) for job in jobs))
    folder = ROOT / "output/online"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
