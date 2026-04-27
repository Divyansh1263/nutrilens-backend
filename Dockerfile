# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ──────────────────────────────────────────────────────────
WORKDIR /app

# ── Dependencies (cached layer — only re-runs when requirements.txt changes) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────────
COPY . .

# ── Runtime configuration ──────────────────────────────────────────────────────
# Cloud Run injects PORT at runtime; 8080 is the default fallback.
ENV PORT=8080

# Informational — Cloud Run routes traffic to $PORT automatically.
EXPOSE 8080

# ── Non-root user (security hardening) ────────────────────────────────────────
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# ── Start server ───────────────────────────────────────────────────────────────
# Shell form required so $PORT resolves at container start time.
# 1 worker + 8 threads matches Cloud Run's recommended concurrency config.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
