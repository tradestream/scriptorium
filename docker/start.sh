#!/bin/sh
# Production entrypoint: run nginx + uvicorn concurrently.
# If either process exits, the container stops.
set -e

# Run database migrations before starting the app
cd /app
python -m alembic upgrade head

# Start nginx in the background
nginx -g "daemon off;" &
NGINX_PID=$!

# Start uvicorn in the background
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 &
UVICORN_PID=$!

# Poll until either process exits (wait -n is bash 4.3+ only, not available in sh/dash)
while kill -0 $NGINX_PID 2>/dev/null && kill -0 $UVICORN_PID 2>/dev/null; do
    sleep 1
done

# One process died; kill the other and exit
kill $NGINX_PID $UVICORN_PID 2>/dev/null || true
exit 1
