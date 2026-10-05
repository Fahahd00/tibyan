# Tibyan backend in one container (a Hugging Face Docker Space): PostgreSQL 16 + pgvector, the AI service and the API.
# Build context: a folder laid out like the repository (scripts/stage-backend.sh assembles it). The indexed corpus is
# not in the image: start.sh restores it from a private dataset (CORPUS_REPO, read with the CORPUS_TOKEN secret).
# Set at deploy time: OPENAI_API_KEY, INTERNAL_API_TOKEN, ADMIN_TOKEN, IP_HASH_SALT, CORS_ORIGINS, CORPUS_*.

FROM node:22-bookworm-slim AS api
WORKDIR /app
COPY package.json package-lock.json tsconfig.base.json ./
COPY packages/contracts packages/contracts
COPY apps/api apps/api
COPY apps/web/package.json apps/web/
RUN npm ci -w @tibyan/api -w @tibyan/contracts --ignore-scripts \
 && npm run build -w @tibyan/contracts && npm run build -w @tibyan/api \
 && npm ci -w @tibyan/api --omit=dev --ignore-scripts && npm cache clean --force

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# PostgreSQL 16 + pgvector from the PostgreSQL apt repository (no default cluster; ours is created below)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl libstdc++6 \
 && install -d /usr/share/postgresql-common/pgdg /etc/postgresql-common/createcluster.d \
 && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && echo "create_main_cluster = false" > /etc/postgresql-common/createcluster.d/no-main.conf \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-16 postgresql-16-pgvector \
 && rm -rf /var/lib/apt/lists/*
COPY --from=api /usr/local/bin/node /usr/local/bin/node

RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# AI service: dependencies first (cached until pyproject.toml changes), then the code and data
COPY services/ai/pyproject.toml services/ai/pyproject.toml
RUN mkdir -p services/ai/tibyan_ai && touch services/ai/tibyan_ai/__init__.py \
 && pip install "./services/ai[openai]" && pip uninstall -y tibyan-ai
COPY services/ai/tibyan_ai services/ai/tibyan_ai
RUN pip install --no-deps ./services/ai
COPY data data

# API gateway
COPY --from=api /app/package.json package.json
COPY --from=api /app/node_modules node_modules
COPY --from=api /app/packages/contracts packages/contracts
COPY --from=api /app/apps/api apps/api
COPY deploy/backend/start.sh start.sh

USER user
ENV HOME=/home/user \
    PGDATA=/home/user/pgdata \
    DATABASE_URL=postgresql://tibyan@127.0.0.1:5432/tibyan \
    AI_SERVICE_URL=http://127.0.0.1:8000 \
    API_PORT=7860 \
    APP_ENV=production \
    TIBYAN_DATA_DIR=/home/user/app/data \
    FASTEMBED_CACHE_DIR=/home/user/models \
    OPENAI_MODEL=gpt-5.4-mini \
    OPENAI_REASONING_EFFORT=low \
    OPENAI_TTS_MODEL=gpt-4o-mini-tts \
    OPENAI_TTS_VOICE=cedar \
    TTS_PROVIDER=openai

# Embedding model baked in (~2.2 GB) so the container starts without downloading it
RUN python -c "from tibyan_ai.providers.embeddings import FastEmbedProvider as P; P('intfloat/multilingual-e5-large', 1024, '/home/user/models')"

EXPOSE 7860
CMD ["sh", "start.sh"]
