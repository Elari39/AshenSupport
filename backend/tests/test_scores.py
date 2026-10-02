from app.score import score


def test_unreviewed_results_cannot_become_accuracy():
    report = {"outcomes": [{"id": "a", "retrieved": []}]}
    result = score(report, [{"id": "a", "human_reviewed": False, "answer_correct": True}])
    assert result["answer_accuracy"]["rate"] is None


def test_recall_only_counts_top_five_and_human_metrics():
    chunks = [{"document": "a.md", "line_start": i, "line_end": i} for i in range(1, 7)]
    report = {"outcomes": [{"id": "a", "retrieved": chunks}]}
    reviews = [
        {
            "id": "a",
            "reviewer": "reviewer",
            "human_reviewed": True,
            "answer_correct": False,
            "gold_evidence": [
                {"document": "a.md", "line_start": 1, "line_end": 1},
                {"document": "a.md", "line_start": 6, "line_end": 6},
            ],
        }
    ]
    result = score(report, reviews)
    assert result["recall_at_5"]["rate"] == 0.5
    assert result["answer_accuracy"] == {"passed": 0, "total": 1, "rate": 0}
