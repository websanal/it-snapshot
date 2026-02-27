FROM python:3.11-slim

LABEL maintainer="websanal/it-snapshot"
LABEL description="it-snapshot central inventory server"

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Data directory for SQLite (override IT_SNAPSHOT_DB to change path)
RUN mkdir -p /data

EXPOSE 8000

# Configuration via environment variables:
#   IT_SNAPSHOT_API_KEY  (required) — shared secret for X-API-Key header
#   IT_SNAPSHOT_DB       (optional) — SQLite file path, default /data/db.sqlite
ENV IT_SNAPSHOT_API_KEY=""
ENV IT_SNAPSHOT_DB="/data/db.sqlite"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
