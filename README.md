# OpenEval

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1)
![Celery](https://img.shields.io/badge/Celery-5-37814A)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Self-hosted LangSmith/Helicone alternative: trace every LLM call, version prompts and
datasets, run RAG/LLM-judge evals against any provider, and block regressions in CI —
one `docker compose up`, no vendor lock-in.

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

1. Upload a dataset (CSV or JSONL with `input` / `expected_output` / `context` columns — see
   `evals/sample_qa.jsonl`). For RAG metrics, `context` can hold multiple retrieved chunks by
   separating them with a `\n---\n` line; otherwise the whole field is treated as one chunk.
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

## LangChain / LangGraph / raw OpenAI client integrations

```python
# LangChain and LangGraph (LangGraph runs on LangChain's callback system, so this
# covers both - pass the handler as a callback anywhere a chain/graph accepts one)
from sdk.client import OpenEvalClient
from sdk.integrations.langchain import OpenEvalCallbackHandler

handler = OpenEvalCallbackHandler(OpenEvalClient(api_key="oe_..."), tags={"env": "prod"})
llm.invoke("hello", config={"callbacks": [handler]})
```

```python
# Already have an openai.OpenAI() client and don't want to change call sites:
from sdk.integrations.openai import patch_openai_client
patch_openai_client(my_openai_client, OpenEvalClient(api_key="oe_..."))
```

`pip install openeval-sdk[langchain]` or `[openai]` for the optional extras.

## Zero-code tracing (LiteLLM proxy)

Don't want to touch app code at all? Point any OpenAI-compatible client at the bundled
LiteLLM proxy instead of the real provider, and every call is traced automatically:

```bash
cd infra
docker compose --profile proxy up -d litellm-proxy   # off by default, opt-in via --profile
```

```python
import openai
client = openai.OpenAI(base_url="http://localhost:4000/v1", api_key="anything")
client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])
# ^ traced to OpenEval with zero code changes beyond the base_url
```

Requires `OPENEVAL_API_KEY` (and your real provider key) set in `infra/.env`; see
`infra/litellm-proxy/`.

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
- **Organizations/Projects/RBAC**: `POST /api/organizations` (creator becomes `owner`),
  invite members with a role (`owner`/`admin`/`member`/`viewer`), create projects under an
  org. `api/rbac.py:require_role(...)` is a reusable dependency for project-scoped routes.
  Each project also has a monthly trace/eval-run quota (`trace_quota_per_month` /
  `eval_run_quota_per_month`, defaults 1M / 1K); `api/rbac.py:check_quota(...)` counts rows
  created since the 1st of the current UTC month and returns 429 once a project hits its
  limit — enforced on trace ingestion and eval-run creation.
- **Human annotation**: `POST /api/annotations/assign` queues a trace for a reviewer,
  `POST /api/annotations/queue/{id}/submit` records their scores, `POST /api/annotations/kappa`
  computes Cohen's kappa between two annotators on a criterion, `POST /api/annotations/export`
  turns annotations into a new dataset.
- **More metrics**: `semantic_similarity` (local sentence-transformers embeddings, no API
  calls), `json_validity`, `regex_match`, `bleu`, `rouge_l` — all deterministic/local, on top
  of the original 5.
- **RAGAS/DeepEval-backed metrics**: `faithfulness`, `answer_relevance`, and `hallucination`
  are now backed by real `deepeval` metric implementations (`FaithfulnessMetric`,
  `AnswerRelevancyMetric`, `HallucinationMetric`) instead of hand-rolled prompts, plus four
  new metrics: `context_precision` / `context_recall` (DeepEval's `ContextualPrecisionMetric`
  / `ContextualRecallMetric` — the same algorithms RAGAS implements), and
  `context_entity_recall` / `noise_robustness` (RAGAS-only metrics with no DeepEval
  equivalent, implemented as DeepEval `GEval` rubrics matching RAGAS's published
  definitions) — plus `toxicity`, `coherence`, `conciseness` LLM-as-judge metrics
  (`ToxicityMetric` / `GEval`). All run against `judge_model` via a small
  `evaluators/deepeval_llm.py` adapter (`LiteLLMDeepEvalModel`), so any litellm-supported
  provider works, not just OpenAI. **Real `ragas` itself could not be installed**: `ragas`
  0.4.x hard-imports `langchain_community.chat_models.vertexai`, a module removed when
  `langchain-community` hit 0.4 (a legacy langchain-0.3-era dependency chain), while this
  project's `litellm`/`instructor` need `openai>=2.20` — no combination of package versions
  satisfies both, so `deepeval` (which has no such conflict and covers most of the same
  ground) is used instead.
- **Synthetic dataset generation**: `POST /api/datasets/{id}/generate` uses the dataset's own
  rows as seeds and an LLM to produce `variation` (realistic paraphrases) or `adversarial`
  (edge cases / prompt injection) rows as a new dataset version.
- **LangChain / LangGraph / OpenAI client integrations**: see "LangChain / LangGraph / raw
  OpenAI client integrations" above.
- **Zero-code tracing via LiteLLM proxy**: see "Zero-code tracing" above.
- **Self-monitoring**: backend exposes `GET /metrics` (Prometheus format) via
  `prometheus-fastapi-instrumentator` — request latency/count by route, plus custom counters
  in `core/metrics.py` (`openeval_traces_ingested_total`, `openeval_llm_cost_usd_total`,
  `openeval_eval_jobs_total`). `docker compose --profile monitoring up` brings up Prometheus +
  Grafana (pre-provisioned dashboards in `infra/grafana/dashboards/`) + Flower (Celery task
  monitoring UI at :5555).

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

## Why I built it this way

- **LiteLLM everywhere a model gets called** (evals, SDK tracing, zero-code proxy) instead of
  an OpenAI-only client. Provider is a config string, not a code path — swapping
  `openai/gpt-4o` for `ollama/llama3` or `anthropic/claude-*` needs no code change, which is
  the whole point of an eval platform not locking you into one vendor.
- **`judge_model` defaults to a local Ollama model, not GPT-4.** An eval platform that quietly
  bills your OpenAI account on `docker compose up` is a bad first impression. Point it at a
  paid provider explicitly once you've supplied your own key.
- **DeepEval instead of RAGAS for RAG/LLM-judge metrics**, even though RAGAS was the original
  target: real `ragas` 0.4.x hard-imports `langchain_community.chat_models.vertexai`, a module
  removed when `langchain-community` hit 0.4, while this project's `litellm`/`instructor` need
  `openai>=2.20` — no combination of package versions resolves both. Rather than vendor a
  patched fork or freeze the rest of the stack to a legacy langchain, DeepEval covers the same
  ground (including RAGAS-equivalent contextual precision/recall) with no such conflict. The
  two metrics with no DeepEval equivalent (`context_entity_recall`, `noise_robustness`) are
  implemented as GEval rubrics matching RAGAS's published definitions instead of skipping them.
- **Celery for eval runs, not a background `asyncio.Task`.** Eval jobs can run hundreds of rows
  against a real LLM API and take minutes; that needs to survive an API process restart and be
  independently scalable (see `infra/k8s/worker/hpa.yaml`), which a request-scoped async task
  doesn't give you.
- **SSE for eval progress, not WebSockets.** Progress is one-directional (server → client) and
  HTTP-cacheable/proxy-friendly; a full-duplex socket buys nothing here for real cost.
- **Every resource scoped to a project from the start** (`api/rbac.py:check_project_role`)
  rather than bolted onto a single-tenant schema later — multi-tenancy retrofits are where
  authorization bugs live, so traces/datasets/prompts/evals were designed against
  organization → project → role from the first migration that needed them.

## What's scaffolded vs. stubbed

Built and working: ingestion (SDK + LangChain/LangGraph + OpenAI-client-patch + LiteLLM-proxy
zero-code tracing + minimal OTLP/HTTP JSON endpoint), dataset upload/versioning/synthetic
generation, eval engine (17 built-in metrics, several backed by real RAGAS-equivalent/DeepEval
implementations, + custom-metric hook), prompt versioning +
playground + promotion, experiments with significance testing, webhooks, cost/latency
analytics, human annotation queue with Cohen's kappa, organizations/projects/RBAC (every
resource — traces, datasets, prompts, eval runs, experiments, annotations — is scoped to a
project and every route checks the caller's role via `require_role`/`check_project_role`),
Redis rate limiting, SSE eval progress, Prometheus self-monitoring (including the Celery
worker's own counters, via `PROMETHEUS_MULTIPROC_DIR` multiprocess mode — see
`core/metrics.py`/`main.py`) + Grafana dashboards, JWT + scoped (read/write/admin) API key
auth, trace feedback (thumbs up/down + comment), bulk trace-to-dataset export, and a
server-side-filterable trace list (model/full-text search/error/latency/cost/date range, not
just whatever the current page happens to contain).

Frontend (Next.js, `frontend/app/`): login/register, an overview dashboard (traces
today/week, error rate, cost trend, top models, recent runs), a searchable/filterable trace
explorer with inline feedback, dataset management (create/upload/synthetic generation/row
viewer), prompt management (versioning, promote-to-production, playground, unified diff
between versions), eval run creation + live SSE progress, experiment comparison (metric
deltas, significance markers, per-row regressions), an annotation queue (assignee/annotator
pickers backed by `GET /organizations/{id}/members`, not raw user IDs) + Cohen's kappa
calculator, cost/latency analytics charts, and a Settings page to create/revoke scoped API
keys.

Stubbed as a starting point only (not production-hardened): `infra/k8s/*.yaml` (secrets
documented in `infra/k8s/secret.example.yaml` as a template to fill in and apply yourself, or
better, generate via a real secrets manager — Sealed Secrets / External Secrets Operator /
SOPS — rather than `kubectl apply` of plaintext `stringData`; the worker HPA needs KEDA
installed in-cluster — see the comment in `infra/k8s/worker/hpa.yaml`), and the prompt diff
viewer/synthetic-data UI use small dependency-free implementations (a line-diff and manual
JSON forms) rather than Monaco/react-diff-viewer from the original spec — swap in later if
richer editing is worth the added JS payload.

## Testing

```bash
cd backend
pytest   # unit tests for evaluators, stats, eval_service — mocked judge calls, no API cost
```
