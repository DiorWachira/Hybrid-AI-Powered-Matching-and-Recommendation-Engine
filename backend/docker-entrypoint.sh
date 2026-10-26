#!/bin/sh
# Container entry point: apply migrations, then serve the API with one worker.
# One API replica runs at a time, so the migration step is never concurrent.
set -e
cd /app/backend
alembic upgrade head
cd /app
# The API port is reachable only from the reverse proxy on the private network, so
# forwarded client addresses (used for rate limiting) can be trusted.
exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 \
    --workers 1 --proxy-headers --forwarded-allow-ips='*' --no-server-header
