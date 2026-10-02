import argparse
import hashlib
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.llm import generate
from app.retrieval import retrieve
from app.schemas import Answer
from app.tools import execute_tool


def main():
    parser = argparse.ArgumentParser(
        description="Explicit opt-in evaluation; fake scores are not AI accuracy."
    )
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--suite", choices=["smoke", "dev", "test"], required=True)
    parser.add_argument("--provider", choices=["fake", "online"], required=True)
    parser.add_argument("--mode", choices=["vector", "hybrid", "rerank"], default="vector")
    args = parser.parse_args()
    if args.provider != settings().provider:
        raise SystemExit("ASHEN_PROVIDER must match --provider; online configuration must be explicit")
    root = Path(__file__).resolve().parents[2]
    cases = json.loads((root / "evals/datasets/cases.json").read_text(encoding="utf-8"))
    selected = cases[:3] if args.suite == "smoke" else [c for c in cases if c["split"] == args.suite]
    outcomes = []
    for case in selected:
        started = time.perf_counter()
        try:
            chunks = retrieve(case["project_id"], case["question"], mode=args.mode)
            context = {
                "question": case["question"],
                "chunks": chunks,
                "mode": "sandbox",
                "scenario": case["scenario"],
                "clarification_count": 0,
                "observations": [],
            }
            answer = None
            for _ in range(4):
                answer = Answer.model_validate(generate(context))
                if answer.action != "tool":
                    break
                context["observations"].append(
                    execute_tool(answer.tool, "sandbox", case["scenario"], None, False)
                )
            assert answer is not None
            refs = set(answer.citation_ids) | {r for cause in answer.causes for r in cause.citation_ids}
            valid = refs <= {c["id"] for c in chunks}
            outcomes.append(
                {
                    "id": case["id"],
                    "status": "ok" if valid else "invalid_citation",
                    "answer": answer.model_dump(),
                    "retrieved": chunks,
                    "expected_action": case["expected_action"],
                    "action_matches_draft_expectation": answer.action == case["expected_action"],
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
        except Exception as exc:
            outcomes.append(
                {
                    "id": case["id"],
                    "status": "error",
                    "error": getattr(exc, "code", type(exc).__name__),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
    latencies = sorted(row["latency_ms"] for row in outcomes)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "created_at": stamp,
        "suite": args.suite,
        "provider": args.provider,
        "mode": args.mode,
        "model": settings().chat_model or "deterministic-fake-v1",
        "dataset_sha256": hashlib.sha256((root / "evals/datasets/cases.json").read_bytes()).hexdigest(),
        "corpus_manifest_sha256": hashlib.sha256(
            (root / "fixtures/docs/manifest.json").read_bytes()
        ).hexdigest(),
        "human_review": "pending",
        "recall_at_5": None,
        "citation_support_rate": None,
        "answer_accuracy": None,
        "cost": None,
        "automated_contract_passed": sum(row["status"] == "ok" for row in outcomes),
        "total": len(outcomes),
        "p50_ms": statistics.median(latencies),
        "p95_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "outcomes": outcomes,
    }
    folder = root / "evals/reports"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{stamp}-{args.suite}-{args.provider}-{args.mode}"
    (folder / f"{filename}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / f"{filename}.md").write_text(
        f"# Evaluation {stamp}\n\nProvider: {args.provider}; mode: {args.mode}; suite: {args.suite}.\n\n"
        f"Automated output-contract checks: {payload['automated_contract_passed']}/{len(outcomes)}.\n\n"
        f"p50: {payload['p50_ms']} ms; p95: {payload['p95_ms']} ms.\n\n"
        "These checks measure executable contracts, not answer quality. Human annotations are pending; "
        "Recall@5, citation support, accuracy and cost are unknown. Fake results cannot establish online AI performance.\n",
        encoding="utf-8",
    )
    print(folder / f"{filename}.md")


if __name__ == "__main__":
    main()
