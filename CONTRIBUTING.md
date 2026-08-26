# Contributing

## Setup

```bash
cd backend && python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cd ../frontend && npm install
```

`docker compose up` in `infra/` brings up Postgres/Redis if you'd rather not run them locally.

## Running tests

```bash
cd backend
pytest                 # unit + integration tests, mocked judge/LLM calls, no API cost
cd ../frontend
npm run build           # typechecks and builds
```

CI (`.github/workflows/ci.yml`) runs both on every push and PR.

## Making changes

- New evaluator: subclass `evaluators.base.Evaluator`, register it in `evaluators/__init__.py`'s
  `REGISTRY`, add a test in `backend/tests/`.
- New API route: add to `backend/api/`, wire auth/RBAC via `api/deps.py` and `api/rbac.py`
  the same way existing routes do — every resource is scoped to a project.
- Alembic migration: `cd backend && alembic revision -m "description"`, then edit the generated
  file in `alembic/versions/`.

## Pull requests

- Keep commits scoped to one logical change each (not a single dump) — makes review and
  bisecting easier.
- Run `pytest` and `npm run build` locally before pushing; CI will re-run them anyway.
- Describe *why*, not just *what*, in the PR description if the change isn't self-evident.
