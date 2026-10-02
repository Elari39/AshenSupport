"""Score a saved run only from explicit human annotations; never silently grade with an LLM."""

import argparse
import hashlib
import json
from pathlib import Path


def ratio(values):
    return {
        "passed": sum(values),
        "total": len(values),
        "rate": sum(values) / len(values) if values else None,
    }


def score(report, reviews):
    outcomes = {row["id"]: row for row in report["outcomes"]}
    correct: list[bool] = []
    citations: list[bool] = []
    refusals: list[bool] = []
    retrieved_gold, total_gold = 0, 0
    for review in reviews:
        if not review.get("reviewer") or not review.get("human_reviewed"):
            continue
        row = outcomes[review["id"]]
        for field, target in [
            ("answer_correct", correct),
            ("citations_supported", citations),
            ("refusal_or_clarification_correct", refusals),
        ]:
            if type(review.get(field)) is bool:
                target.append(review[field])
        # Gold evidence is stable across DB rebuilds: source document plus inclusive source lines.
        for gold in review.get("gold_evidence", []):
            total_gold += 1
            retrieved_gold += any(
                chunk["document"] == gold["document"]
                and chunk["line_start"] <= gold["line_end"]
                and chunk["line_end"] >= gold["line_start"]
                for chunk in row.get("retrieved", [])[:5]
            )
    return {
        "answer_accuracy": ratio(correct),
        "citation_support": ratio(citations),
        "refusal_or_clarification": ratio(refusals),
        "recall_at_5": {
            "retrieved": retrieved_gold,
            "relevant": total_gold,
            "rate": retrieved_gold / total_gold if total_gold else None,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--annotations", type=Path)
    args = parser.parse_args()
    raw = args.report.read_bytes()
    report = json.loads(raw)
    if not args.annotations:
        output = args.report.with_suffix(".review.json")
        if output.exists():
            raise SystemExit("Review file already exists; refusing to overwrite human work")
        template = {
            "report_sha256": hashlib.sha256(raw).hexdigest(),
            "reviews": [
                {
                    "id": row["id"],
                    "reviewer": "",
                    "human_reviewed": False,
                    "answer_correct": None,
                    "citations_supported": None,
                    "refusal_or_clarification_correct": None,
                    "gold_evidence": [],
                    "notes": "",
                }
                for row in report["outcomes"]
            ],
        }
        output.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
        if annotations["report_sha256"] != hashlib.sha256(raw).hexdigest():
            raise SystemExit("Review does not match this report")
        reviews = annotations["reviews"]
        ids = [review["id"] for review in reviews]
        if len(ids) != len(set(ids)) or not set(ids) <= {row["id"] for row in report["outcomes"]}:
            raise SystemExit("Duplicate or unknown review IDs")
        output = args.report.with_suffix(".scored.json")
        output.write_text(
            json.dumps(
                {
                    "source_report_sha256": hashlib.sha256(raw).hexdigest(),
                    "provider": report["provider"],
                    **score(report, reviews),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    print(output)


if __name__ == "__main__":
    main()
