#!/bin/bash
# `wait -n` needs bash - /bin/sh is dash on this image and lacks the flag.
set -e

alembic upgrade head

# Free Render plans don't offer a separate Background Worker service, so the
# Celery worker runs as a second process in this same container instead of
# its own service - `wait -n` keeps the container alive on either process's
# exit, not just uvicorn's.
# --pool=solo, concurrency 1: default prefork spawns 8 worker processes,
# each loading torch/transformers/sentence-transformers - blew past the
# free tier's 512MB RAM cap immediately. One process is plenty for demo
# eval-job volume.
celery -A workers.celery_app worker --loglevel=info -Q evals --pool=solo --concurrency=1 &
# Render assigns its own $PORT (health checks target it specifically, not
# just any open port) and doesn't set it locally, so default to 8000 to
# match docker-compose's hardcoded mapping there.
uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" &
wait -n
