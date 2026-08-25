from string import Template

from sqlalchemy.orm import Session

from evaluators import get_evaluator
from models.dataset import DatasetRow
from models.eval import EvalResult, EvalRun
from models.prompt import PromptTemplate
from services.stats import percentile, welch_t_test


def render_prompt(template: PromptTemplate | None, input_text: str) -> str:
    if template is None:
        return input_text
    return Template(template.template).safe_substitute(input=input_text)


def render_prompt_vars(template_str: str, variables: dict) -> str:
    """$-style substitution (stdlib string.Template), matching render_prompt above.
    Unknown/missing variables are left as literal $placeholders (safe_substitute).
    """
    return Template(template_str).safe_substitute(**variables)


def run_eval_row(*, judge_model: str, metrics: list[str], row: DatasetRow, output: str) -> dict:
    scores = {}
    for metric_name in metrics:
        evaluator = get_evaluator(metric_name)
        scores[metric_name] = evaluator.score(
            input=row.input,
            output=output,
            expected_output=row.expected_output,
            context=row.context,
            judge_model=judge_model,
        )
    return scores


def summarize_run(db: Session, eval_run: EvalRun) -> dict:
    all_results = db.query(EvalResult).filter(EvalResult.eval_run_id == eval_run.id).all()
    results = [r for r in all_results if r.error is None]
    if not results:
        return {"row_count": 0, "failed_row_count": len(all_results)}

    latencies = [r.latency_ms for r in results]
    costs = [r.cost_usd for r in results]
    metric_avgs: dict[str, float] = {}
    for metric in eval_run.metrics:
        vals = [r.scores.get(metric, 0.0) for r in results if metric in r.scores]
        metric_avgs[metric] = sum(vals) / len(vals) if vals else 0.0

    return {
        "row_count": len(results),
        "failed_row_count": len(all_results) - len(results),
        "avg_scores": metric_avgs,
        "total_cost_usd": sum(costs),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
    }


def compare_runs(db: Session, run_ids: list, regression_threshold: float = 0.05) -> dict:
    """Compare N eval runs against the first run in run_ids (the baseline).
    Returns per-run metric deltas, per-row diffs vs baseline, Welch's t-test
    significance per metric, and a naive regression flag list.
    """
    runs = db.query(EvalRun).filter(EvalRun.id.in_(run_ids)).all()
    runs_by_id = {str(r.id): r for r in runs}
    ordered = [runs_by_id[str(rid)] for rid in run_ids if str(rid) in runs_by_id]
    if not ordered:
        return {"baseline_run_id": None, "runs": []}
    baseline = ordered[0]

    baseline_results = {str(r.dataset_row_id): r for r in db.query(EvalResult).filter(EvalResult.eval_run_id == baseline.id).all()}

    comparison = []
    for run in ordered:
        is_baseline = run.id == baseline.id
        deltas = {}
        significance = {}
        for metric, baseline_score in baseline.summary.get("avg_scores", {}).items():
            current_score = run.summary.get("avg_scores", {}).get(metric, 0.0)
            deltas[metric] = current_score - baseline_score

            if not is_baseline:
                run_results = db.query(EvalResult).filter(EvalResult.eval_run_id == run.id).all()
                baseline_scores = [r.scores.get(metric) for r in baseline_results.values() if metric in r.scores]
                candidate_scores = [r.scores.get(metric) for r in run_results if metric in r.scores]
                significance[metric] = welch_t_test(baseline_scores, candidate_scores)

        regressions = [m for m, d in deltas.items() if m != "hallucination" and d < -regression_threshold]
        if "hallucination" in deltas and deltas["hallucination"] > regression_threshold:
            regressions.append("hallucination")

        row_diffs = []
        if not is_baseline:
            run_results = db.query(EvalResult).filter(EvalResult.eval_run_id == run.id).all()
            for result in run_results:
                base = baseline_results.get(str(result.dataset_row_id))
                if not base:
                    continue
                per_metric_delta = {
                    m: result.scores.get(m, 0.0) - base.scores.get(m, 0.0)
                    for m in set(result.scores) | set(base.scores)
                }
                if any(abs(d) > regression_threshold for d in per_metric_delta.values()):
                    row_diffs.append(
                        {
                            "dataset_row_id": str(result.dataset_row_id),
                            "baseline_output": base.output,
                            "candidate_output": result.output,
                            "delta": per_metric_delta,
                        }
                    )

        comparison.append(
            {
                "eval_run_id": str(run.id),
                "name": run.name,
                "summary": run.summary,
                "delta_vs_baseline": deltas if not is_baseline else {},
                "significance_vs_baseline": significance,
                "regressions": regressions if not is_baseline else [],
                "row_diffs": row_diffs,
            }
        )

    return {"baseline_run_id": str(baseline.id), "runs": comparison}
