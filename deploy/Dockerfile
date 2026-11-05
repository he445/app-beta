# Motor de análise + API. O mesmo contêiner vai da nuvem (PoC) ao servidor interno (piloto).
# Construa da raiz do repositório: docker build -f deploy/Dockerfile -t qa-engine .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    QA_DATA_DIR=/data \
    QA_PROFILES_DIR=/app/profiles \
    QA_CONTRACTS_DIR=/app/contracts

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app/engine
COPY engine/pyproject.toml engine/uv.lock engine/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY engine/src ./src
RUN uv sync --frozen --no-dev
COPY contracts /app/contracts
COPY profiles /app/profiles

RUN useradd --create-home --uid 10001 qa && mkdir -p /data && chown qa /data
USER qa
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["/app/engine/.venv/bin/python", "-m", "qa_engine.entrypoints.http"]
