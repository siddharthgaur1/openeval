#!/bin/sh
set -e

alembic upgrade head

# Free Render plans don't offer a separate Background Worker service, so the
# Celery worker runs as a second process in this same container instead of
# its own service - `wait -n` keeps the container alive on either process's
# exit, not just uvicorn's.
celery -A workers.celery_app worker --loglevel=info -Q evals &
uvicorn main:app --host 0.0.0.0 --port 8000 &
wait -n
