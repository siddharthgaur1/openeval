from types import SimpleNamespace

from services.annotation_service import cohen_kappa, export_annotations_as_dataset_rows


def test_cohen_kappa_perfect_agreement():
    assert cohen_kappa([1, 2, 3, 1, 2], [1, 2, 3, 1, 2]) == 1.0


def test_cohen_kappa_no_agreement_beyond_chance():
    # Two annotators who always disagree, evenly split labels
    a = ["yes", "no", "yes", "no"]
    b = ["no", "yes", "no", "yes"]
    kappa = cohen_kappa(a, b)
    assert kappa < 0  # worse than chance


def test_cohen_kappa_empty_returns_zero():
    assert cohen_kappa([], []) == 0.0


def test_cohen_kappa_mismatched_lengths_returns_zero():
    assert cohen_kappa([1, 2], [1]) == 0.0


def test_export_annotations_as_dataset_rows_maps_trace_and_scores():
    trace_id = "trace-1"
    trace = SimpleNamespace(id=trace_id, prompt="What is 2+2?", response="4")
    annotation = SimpleNamespace(trace_id=trace_id, scores={"coherence": 5}, comment="good", annotator_id="ann-1")

    rows = export_annotations_as_dataset_rows([annotation], {trace_id: trace})

    assert rows == [
        {
            "input": "What is 2+2?",
            "expected_output": "4",
            "context": None,
            "tags": {"scores": {"coherence": 5}, "comment": "good", "annotator_id": "ann-1"},
        }
    ]


def test_export_annotations_skips_missing_trace():
    annotation = SimpleNamespace(trace_id="missing", scores={}, comment=None, annotator_id="ann-1")
    assert export_annotations_as_dataset_rows([annotation], {}) == []
