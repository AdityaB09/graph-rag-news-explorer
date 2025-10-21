FROM python:3.11-slim

# System deps (curl for healthcheck; build tools only if you compile wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Python deps (cached layer) ----
COPY requirements.txt /app/requirements.txt
# Recommended: use psycopg2-binary>=2.9.9 in requirements.txt for Neon SSL/channel binding
ENV PIP_NO_CACHE_DIR=1
RUN pip install -r requirements.txt

# spaCy English model (pinned to match spacy 3.7.x)
RUN pip install \
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# ---- App code ----
COPY app /app/app

ENV PYTHONUNBUFFERED=1

# Healthcheck hits /health
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s CMD curl -fsS http://127.0.0.1:${PORT:-8080}/health || exit 1

# IMPORTANT: accept Render's $PORT (falls back to 8080 locally)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
