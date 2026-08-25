from datetime import datetime
from types import SimpleNamespace

from services.analytics_service import cost_by_day, cost_by_model, latency_by_model, project_monthly_cost, usage_by_tag


def _trace(model="gpt-4o-mini", cost=0.01, latency=100, day="2026-08-01", tags=None):
    return SimpleNamespace(
        model=model,
        cost_usd=cost,
        latency_ms=latency,
        created_at=datetime.fromisoformat(day),
        tags=tags or {},
    )


def test_cost_by_model_sums_per_model():
    traces = [_trace(model="a", cost=1.0), _trace(model="a", cost=2.0), _trace(model="b", cost=5.0)]
    assert cost_by_model(traces) == {"a": 3.0, "b": 5.0}


def test_cost_by_day_groups_and_sorts():
    traces = [_trace(day="2026-08-02", cost=1.0), _trace(day="2026-08-01", cost=2.0)]
    result = cost_by_day(traces)
    assert list(result.keys()) == ["2026-08-01", "2026-08-02"]
    assert result["2026-08-01"] == 2.0


def test_project_monthly_cost_scales_by_days_elapsed():
    traces = [_trace(day="2026-08-01", cost=10.0), _trace(day="2026-08-05", cost=10.0)]
    # 20 spent by day 5 of a 31-day month -> 20/5*31 = 124
    projected = project_monthly_cost(traces, as_of=datetime(2026, 8, 5))
    assert projected == 124.0


def test_project_monthly_cost_empty_traces_returns_zero():
    assert project_monthly_cost([], as_of=datetime(2026, 8, 5)) == 0.0


def test_latency_by_model_computes_percentiles():
    traces = [_trace(model="a", latency=l) for l in [10, 20, 30, 40, 50]]
    result = latency_by_model(traces)
    assert result["a"]["p50"] == 30


def test_usage_by_tag_counts_values():
    traces = [_trace(tags={"env": "prod"}), _trace(tags={"env": "prod"}), _trace(tags={"env": "dev"})]
    assert usage_by_tag(traces, "env") == {"prod": 2, "dev": 1}
