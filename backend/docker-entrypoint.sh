#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Initializing database..."
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
