# Multi-stage build for Scriptorium backend

# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /tmp
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml pyproject.toml
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install .


# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install Calibre CLI tools and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    calibre \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create data directories
RUN mkdir -p /app/data/{library,ingest,config,covers}

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Startup script: migrate then serve
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

CMD ["/app/docker-entrypoint.sh"]
