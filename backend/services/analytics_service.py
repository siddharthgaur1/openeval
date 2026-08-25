from collections import defaultdict
from datetime import datetime

from models.trace import Trace
from services.stats import percentile


def cost_by_model(traces: list[Trace]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for t in traces:
        totals[t.model] += t.cost_usd
    return dict(totals)


def cost_by_day(traces: list[Trace]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for t in traces:
        day = t.created_at.date().isoformat()
        totals[day] += t.cost_usd
    return dict(sorted(totals.items()))


def project_monthly_cost(traces: list[Trace], as_of: datetime | None = None) -> float:
    """Naive projection: (cost so far this month / days elapsed) * days in month."""
    as_of = as_of or datetime.utcnow()
    this_month = [t for t in traces if t.created_at.year == as_of.year and t.created_at.month == as_of.month]
    if not this_month:
        return 0.0
    spent = sum(t.cost_usd for t in this_month)
    days_elapsed = max(1, as_of.day)
    days_in_month = _days_in_month(as_of.year, as_of.month)
    return round(spent / days_elapsed * days_in_month, 6)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    next_month = datetime(year, month + 1, 1)
    return (next_month - datetime(year, month, 1)).days


def latency_by_model(traces: list[Trace]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for t in traces:
        grouped[t.model].append(t.latency_ms)
    return {
        model: {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        }
        for model, latencies in grouped.items()
    }


def usage_by_tag(traces: list[Trace], tag_key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for t in traces:
        value = (t.tags or {}).get(tag_key)
        if value is not None:
            counts[str(value)] += 1
    return dict(counts)
