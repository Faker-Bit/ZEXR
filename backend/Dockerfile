# ---------------------------------------------------------------------------
# LimeDeals API container.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps for psycopg / lxml, removed from the runtime layer.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "psycopg[binary]>=3.2" \
 && apt-get purge -y build-essential libpq-dev \
 && apt-get autoremove -y

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY tools ./tools

RUN useradd --create-home --uid 10001 limedeals && chown -R limedeals:limedeals /app
USER limedeals

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]