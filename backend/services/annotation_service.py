from collections import Counter


def cohen_kappa(labels_a: list, labels_b: list) -> float:
    """Cohen's kappa for inter-annotator agreement between two annotators who
    scored the same items (labels_a[i] and labels_b[i] must be the i-th item's
    label from each). Works for any hashable label (categorical, binary, or
    an int/float rating treated categorically).
    """
    if len(labels_a) != len(labels_b) or not labels_a:
        return 0.0

    n = len(labels_a)
    observed_agreement = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n

    counts_a = Counter(labels_a)
    counts_b = Counter(labels_b)
    categories = set(counts_a) | set(counts_b)
    expected_agreement = sum((counts_a.get(c, 0) / n) * (counts_b.get(c, 0) / n) for c in categories)

    if expected_agreement == 1.0:
        return 1.0
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


def export_annotations_as_dataset_rows(annotations: list, traces_by_id: dict) -> list[dict]:
    """Turn a list of Annotation rows into dataset-row dicts (input/expected_output/
    context/tags), pulling the underlying trace's prompt/response and folding the
    annotator's scores + comment into tags.
    """
    rows = []
    for annotation in annotations:
        trace = traces_by_id.get(annotation.trace_id)
        if not trace:
            continue
        rows.append(
            {
                "input": trace.prompt,
                "expected_output": trace.response,
                "context": None,
                "tags": {"scores": annotation.scores, "comment": annotation.comment, "annotator_id": str(annotation.annotator_id)},
            }
        )
    return rows
