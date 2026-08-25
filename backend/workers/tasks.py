import time
from datetime import datetime

from litellm import completion, completion_cost

from core.database import SessionLocal
from core.metrics import eval_jobs_total
from core.redis import publish_progress
from models.dataset import Dataset
from models.eval import EvalResult, EvalRun
from models.prompt import PromptTemplate
from services.eval_service import render_prompt, run_eval_row, summarize_run
from services.webhook_service import build_payload, eval_run_events, webhooks_for_event
from workers.celery_app import celery_app
from workers.webhook_tasks import deliver_webhook

ROW_MAX_RETRIES = 1


def _run_single_row(*, eval_run: EvalRun, template, row):
    prompt = render_prompt(template, row.input)
    start = time.perf_counter()
    response = completion(model=eval_run.target_model, messages=[{"role": "user", "content": prompt}])
    latency_ms = (time.perf_counter() - start) * 1000
    output = response.choices[0].message.content or ""
    try:
        cost = completion_cost(completion_response=response)
    except Exception:
        cost = 0.0
    scores = run_eval_row(judge_model=eval_run.judge_model, metrics=eval_run.metrics, row=row, output=output)
    return EvalResult(
        eval_run_id=eval_run.id,
        dataset_row_id=row.id,
        output=output,
        scores=scores,
        latency_ms=latency_ms,
        cost_usd=cost,
    )


@celery_app.task(name="workers.tasks.run_eval_job", bind=True, max_retries=2)
def run_eval_job(self, eval_run_id: str):
    db = SessionLocal()
    try:
        eval_run = db.query(EvalRun).filter(EvalRun.id == eval_run_id).first()
        if not eval_run:
            return

        dataset = db.query(Dataset).filter(Dataset.id == eval_run.dataset_id).first()
        template = (
            db.query(PromptTemplate).filter(PromptTemplate.id == eval_run.prompt_template_id).first()
            if eval_run.prompt_template_id
            else None
        )

        eval_run.status = "running"
        eval_run.total_rows = len(dataset.rows)
        eval_run.completed_rows = 0
        eval_run.failed_rows = 0
        db.commit()
        publish_progress(str(eval_run.id), {"status": "running", "total_rows": eval_run.total_rows, "completed_rows": 0, "failed_rows": 0})

        for row in dataset.rows:
            attempt = 0
            while True:
                try:
                    result = _run_single_row(eval_run=eval_run, template=template, row=row)
                    db.add(result)
                    eval_run.completed_rows += 1
                    break
                except Exception as exc:
                    attempt += 1
                    if attempt > ROW_MAX_RETRIES:
                        db.add(EvalResult(eval_run_id=eval_run.id, dataset_row_id=row.id, error=str(exc)))
                        eval_run.failed_rows += 1
                        break
            db.commit()
            publish_progress(
                str(eval_run.id),
                {
                    "status": "running",
                    "total_rows": eval_run.total_rows,
                    "completed_rows": eval_run.completed_rows,
                    "failed_rows": eval_run.failed_rows,
                },
            )

        eval_run.summary = summarize_run(db, eval_run)
        eval_run.status = "completed" if eval_run.failed_rows < eval_run.total_rows else "failed"
        eval_run.finished_at = datetime.utcnow()
        eval_jobs_total.labels(status=eval_run.status).inc()
        db.commit()
        publish_progress(
            str(eval_run.id),
            {"status": eval_run.status, "total_rows": eval_run.total_rows, "completed_rows": eval_run.completed_rows, "failed_rows": eval_run.failed_rows, "summary": eval_run.summary},
        )

        for event in eval_run_events(eval_run):
            for webhook in webhooks_for_event(db, eval_run.user_id, event):
                deliver_webhook.delay(str(webhook.id), build_payload(event, eval_run))
    finally:
        db.close()
