#!/bin/bash

# Ensure output is not buffered
export PYTHONUNBUFFERED=1

# Start Celery worker in background (green)
stdbuf -oL celery -A app.jobs.celery_worker worker --loglevel=info 2>&1 | stdbuf -oL sed 's/^/\x1b[32m[CELERY]\x1b[0m /' &

# Start Uvicorn in background (blue)
stdbuf -oL uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | stdbuf -oL sed 's/^/\x1b[34m[UVICORN]\x1b[0m /' &

# Wait for all background jobs
wait