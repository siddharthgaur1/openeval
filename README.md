# OpenEval

Self-hostable LLM evaluation & observability platform. Trace every LLM call,
version your prompts and datasets, run evals with an LLM judge, and catch
regressions before they ship.

## Architecture

```
                       ┌────────────────┐
   Your app  ───SDK───▶│  FastAPI API   │───────┐
   (or OTLP) ──trace───▶│  (backend/)    │       │
                       └───────┬────────┘       │
                               │                 ▼
                        ┌──────▼──────┐   ┌─────────────┐
                        │  PostgreSQL │   │    Redis     │
                        │ traces,     │   │ job queue /  │
                        │ datasets,   │   │ cache        │
                        │ evals       │   └──────┬──────┘
                        └─────────────┘          │
                                           ┌──────▼───────┐
                                           │ Celery worker │
                                           │ (evaluators:  │
                                           │ faithfulness, │
                                           │ relevance,    │
                                           │ hallucination,│
                                           │ exact/F1)     │
                                           │ via LiteLLM   │
                                           └───────────────┘
                               ▲
                        ┌──────┴────────┐
                        │  Next.js UI   │
                        │ (frontend/)   │
                        └───────────────┘
```

## Quickstart

```bash
cd infra
cp .env.example .env   # fill in JWT_SECRET; leave provider keys empty to stay local-only
docker compose up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- UI: http://localhost:3000

Run migrations (done automatically by the `backend` container on startup, or manually):

```bash
docker compose exec backend alembic upgrade head
```

Register a user and mint an API key:

```bash
curl -X POST localhost:8000/api/auth/register -d '{"email":"you@example.com","password":"pw"}' -H 'Content-Type: application/json'
# -> {"access_token": "..."}

curl -X POST localhost:8000/api/auth/api-keys -H "Authorization: Bearer <access_token>" \
  -d '{"name":"local-dev"}' -H 'Content-Type: application/json'
# -> {"key": "oe_...", ...}  save this, it's shown once
```

## SDK usage

```python
from sdk.client import OpenEvalClient

client = OpenEvalClient(api_key="oe_...", base_url="http://localhost:8000")

response = client.completion(
    model="ollama/llama3",           # any LiteLLM-supported model: openai/gpt-4o, anthropic/claude-..., ollama/llama3, gemini/...
    messages=[{"role": "user", "content": "Hello!"}],
    tags={"env": "dev", "feature": "chat"},
)
```

Every call is auto-logged: prompt, response, latency, token counts, cost, model, tags —
visible immediately in the Traces dashboard.

## Running an eval

1. Upload a dataset (CSV or JSONL with `input` / `expected_output` / `context` columns — see `evals/sample_qa.jsonl`):
   ```bash
   curl -X POST "localhost:8000/api/datasets/upload?name=sample-qa" \
     -H "Authorization: Bearer oe_..." -F "file=@evals/sample_qa.jsonl"
   ```
2. Trigger a run:
   ```bash
   curl -X POST localhost:8000/api/evals -H "Authorization: Bearer oe_..." -H 'Content-Type: application/json' -d '{
     "dataset_id": "<dataset-id>",
     "target_model": "ollama/llama3",
     "metrics": ["exact_match", "f1", "answer_relevance", "faithfulness", "hallucination"]
   }'
   ```
3. Watch progress in the Eval Runs dashboard, or poll `GET /api/evals/{id}`.

Compare two runs and detect regressions:
```bash
curl -X POST localhost:8000/api/evals/compare -H "Authorization: Bearer oe_..." -d '{"run_ids": ["<baseline>", "<candidate>"]}'
```

## More: experiments, webhooks, analytics, playground

- **Experiments**: `POST /api/experiments` groups eval runs with a pinned baseline; `GET
  /api/experiments/{id}/compare` returns metric deltas, per-row diffs, and Welch's t-test
  significance per metric vs. the baseline.
- **Webhooks**: `POST /api/webhooks` registers a URL for `eval.completed`,
  `eval.regression_detected`, or `eval.passed` (HMAC-signed via `X-OpenEval-Signature` if you
  set a `secret`). Fired automatically when an eval run finishes or a compare call detects a
  regression.
- **Live progress**: `GET /api/evals/{id}/status` is a Server-Sent Events stream of row-by-row
  eval progress (`completed_rows`/`failed_rows`/`total_rows`), shown as a progress bar in the
  eval run detail page.
- **Analytics**: `GET /api/analytics/cost`, `/latency`, `/usage` — cost by model/day with a
  naive monthly projection, p50/p95/p99 latency by model, usage by tag.
- **Prompt playground & promotion**: `POST /api/prompts/{version_id}/playground` renders a
  prompt version against any model without saving anything; `POST
  /api/prompts/{version_id}/promote` atomically marks one version `production` and demotes the
  previous production version to `staging`.
- **Rate limiting**: every authenticated request is checked against a Redis sliding-window
  limit (`rate_limit_per_minute` in `.env`, default 120/min per user).
- **More metrics**: `semantic_similarity` (local sentence-transformers embeddings, no API
  calls), `json_validity`, `regex_match`, `bleu`, `rouge_l` — all deterministic/local, on top
  of the original 5.

## CI/CD integration

`.github/actions/run-eval` is a composite GitHub Action that triggers an eval run against a
pinned dataset, polls until it finishes, and comments the results on the PR. See
`.github/workflows/eval-on-pr.yml` for wiring; set repo vars `OPENEVAL_API_URL`,
`OPENEVAL_DATASET_ID`, `OPENEVAL_TARGET_MODEL` and secret `OPENEVAL_API_KEY`.

## Cost

The default judge model is `ollama/llama3` (local, free) so a fresh install never calls a
paid API. Point `target_model` / `judge_model` at `openai/...`, `anthropic/...`, etc. only
when you've supplied your own provider key in `infra/.env`.

## Project structure

See top of this repo for `backend/` (FastAPI + Celery + SDK), `frontend/` (Next.js),
`infra/` (docker-compose, k8s starting points, Prometheus scrape config), `evals/`
(example datasets), `.github/` (CI + PR eval action).

## What's scaffolded vs. stubbed

Built and working: ingestion (SDK + minimal OTLP/HTTP JSON endpoint), dataset upload/versioning,
eval engine (5 built-in metrics + custom-metric hook), prompt versioning, run comparison with
regression detection, JWT + API key auth, traces/eval dashboards.

Stubbed as a starting point only (not production-hardened): `infra/k8s/*.yaml` (no HPA/secrets
management), `infra/prometheus/prometheus.yml` (backend doesn't expose `/metrics` yet — add
`prometheus-fastapi-instrumentator` when needed), Grafana dashboards (not included).

## Testing

```bash
cd backend
pytest   # unit tests for evaluators, stats, eval_service — mocked judge calls, no API cost
```
