"""Fail the job when an eval run misses its thresholds.

Thresholds are comma-separated: `metric>=min` for scores where higher is better,
`metric<=max` where lower is better (hallucination). A metric with a threshold but
no score fails, so a renamed or dropped metric can't turn the gate off silently.
"""

import json
import re
import sys

THRESHOLD = re.compile(r"^\s*([\w-]+)\s*(>=|<=)\s*([0-9]*\.?[0-9]+)\s*$")


def parse_thresholds(spec: str) -> list[tuple[str, str, float]]:
    thresholds = []
    for part in filter(str.strip, spec.split(",")):
        match = THRESHOLD.match(part)
        if not match:
            raise ValueError(f"bad threshold {part!r}: use metric>=0.8 or metric<=0.2")
        thresholds.append((match[1], match[2], float(match[3])))
    return thresholds


def find_failures(result: dict, thresholds: list[tuple[str, str, float]]) -> list[str]:
    if result.get("status") != "completed":
        return [f"eval run status is {result.get('status')!r}, not 'completed'"]
    scores = (result.get("summary") or {}).get("avg_scores") or {}
    failures = []
    for metric, op, limit in thresholds:
        score = scores.get(metric)
        if score is None:
            failures.append(f"{metric}: no score in this run")
        elif (op == ">=" and score < limit) or (op == "<=" and score > limit):
            failures.append(f"{metric}: {score:.3f}, required {op} {limit}")
    return failures


def main(result_path: str, spec: str) -> int:
    with open(result_path, encoding="utf-8") as f:
        result = json.load(f)
    failures = find_failures(result, parse_thresholds(spec))
    for failure in failures:
        print(f"::error::OpenEval gate: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
