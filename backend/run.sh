#!/bin/bash
# Scriptorium Backend startup script

set -e

echo "Starting Scriptorium Backend..."

VENV=".venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

# Install / sync dependencies
if [ ! -f "$VENV/bin/alembic" ]; then
    echo "Installing dependencies..."
    "$VENV/bin/pip" install -e . -q
fi

# Create data directories
mkdir -p data/{library,ingest,config,covers}

# Run database migrations (using venv alembic, not system one)
echo "Running database migrations..."
"$VENV/bin/alembic" upgrade head

# Initialize database
echo "Initializing database..."
"$VENV/bin/python" -c "import asyncio; from app.database import init_db; asyncio.run(init_db())" || true

# Start server
echo "Starting uvicorn server on http://localhost:8000"
"$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload
