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

# Start uvicorn in the foreground
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 &
UVICORN_PID=$!

# Wait for either process to exit; if one dies, kill the other
wait -n $NGINX_PID $UVICORN_PID
EXIT_CODE=$?

kill $NGINX_PID $UVICORN_PID 2>/dev/null || true
exit $EXIT_CODE
