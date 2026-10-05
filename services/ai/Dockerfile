# Tibyan AI service (FastAPI). Build context: repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) Dependencies only (cached until pyproject.toml changes)
COPY services/ai/pyproject.toml services/ai/pyproject.toml
RUN mkdir -p services/ai/tibyan_ai && touch services/ai/tibyan_ai/__init__.py \
 && pip install "./services/ai[openai]" && pip uninstall -y tibyan-ai

# 2) Application code + version-controlled data (registry, escalation bodies, corpus snapshots, eval set)
COPY services/ai/tibyan_ai services/ai/tibyan_ai
RUN pip install --no-deps ./services/ai
COPY data data

RUN useradd --uid 10001 --create-home tibyan && mkdir -p /models && chown tibyan /models
USER tibyan

ENV TIBYAN_DATA_DIR=/app/data \
    FASTEMBED_CACHE_DIR=/models

EXPOSE 8000
CMD ["uvicorn", "tibyan_ai.main:app", "--host", "0.0.0.0", "--port", "8000"]
