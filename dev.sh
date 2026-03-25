#!/bin/bash
# Local development against NAS database
#
# Prerequisites:
#   1. /Volumes/docker/ is mounted (SMB share to NAS)
#   2. Docker container on NAS is stopped: docker stop scriptorium
#
# Usage: ./dev.sh [start|stop|migrate|status]

set -e

NAS_DB="/Volumes/docker/scriptorium/data/config/scriptorium.db"
BACKEND_DIR="$(cd "$(dirname "$0")/backend" && pwd)"
FRONTEND_DIR="$(cd "$(dirname "$0")/frontend" && pwd)"

case "${1:-start}" in
  status)
    echo "=== NAS Database ==="
    if [ -f "$NAS_DB" ]; then
      echo "  Found: $NAS_DB ($(du -h "$NAS_DB" | cut -f1))"
      sqlite3 "$NAS_DB" "SELECT 'Migration: ' || version_num FROM alembic_version;" 2>/dev/null || echo "  (locked — stop NAS container first)"
    else
      echo "  Not found — is /Volumes/docker/ mounted?"
    fi
    echo ""
    echo "=== Backend ==="
    curl -s http://localhost:8000/health 2>/dev/null && echo "" || echo "  Not running"
    echo "=== Frontend ==="
    curl -s -o /dev/null -w "  Running on http://localhost:5173 (status %{http_code})\n" http://localhost:5173 2>/dev/null || echo "  Not running"
    ;;

  migrate)
    echo "Running migrations against NAS database..."
    cd "$BACKEND_DIR"
    cp .env.local .env
    python -m alembic upgrade head
    echo "✓ Migrations complete"
    ;;

  start)
    if ! [ -f "$NAS_DB" ]; then
      echo "❌ NAS database not found. Is /Volumes/docker/ mounted?"
      exit 1
    fi

    echo "=== Starting Scriptorium local dev ==="
    cd "$BACKEND_DIR"
    cp .env.local .env

    echo "Running migrations..."
    python -m alembic upgrade head 2>&1 | tail -3

    echo "Starting backend (port 8000)..."
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!

    echo "Starting frontend (port 5173)..."
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!

    echo ""
    echo "✓ Backend:  http://localhost:8000  (PID $BACKEND_PID)"
    echo "✓ Frontend: http://localhost:5173  (PID $FRONTEND_PID)"
    echo ""
    echo "Press Ctrl+C to stop both servers"

    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo 'Servers stopped. Run: docker start scriptorium (on NAS) to resume production.'" EXIT
    wait
    ;;

  stop)
    echo "Stopping local servers..."
    pkill -f "uvicorn app.main" 2>/dev/null && echo "  Backend stopped" || echo "  Backend not running"
    pkill -f "vite.*scriptorium" 2>/dev/null && echo "  Frontend stopped" || echo "  Frontend not running"
    echo ""
    echo "Don't forget: docker start scriptorium (on NAS)"
    ;;

  deploy)
    echo "=== Deploying to NAS ==="
    echo "Committing..."
    git add -A
    git status --short
    read -p "Commit message: " MSG
    git commit -m "$MSG

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
    git push origin main

    # Get current version and bump patch
    CURRENT=$(git tag -l 'v*' | sort -V | tail -1)
    echo "Current version: $CURRENT"
    read -p "New version tag (or Enter to skip): " TAG
    if [ -n "$TAG" ]; then
      git tag -a "$TAG" -m "$TAG"
      git push origin "$TAG"
      echo "✓ Tagged $TAG — Docker build will start on GitHub Actions"
      echo "  Monitor: gh run list --limit 1"
    fi
    ;;

  *)
    echo "Usage: ./dev.sh [start|stop|migrate|status|deploy]"
    ;;
esac
