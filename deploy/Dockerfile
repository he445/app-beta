# Uma imagem com o motor de análise e a interface na mesma origem (ADR-0010): o
# celular abre um endereço só, sem CORS e sem VITE_API_URL. O mesmo contêiner vai da
# nuvem (PoC) ao servidor interno (piloto).
# Construa da raiz do repositório: docker build -f deploy/Dockerfile -t qa-digitalizacao .

# 1. Interface (site estático), com o motor na mesma origem (VITE_API_URL vazio).
FROM node:22-slim AS ui
WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
ENV VITE_API_URL=""
RUN npm run build

# 2. Motor + interface compilada + lote de demonstração.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    QA_DATA_DIR=/data \
    QA_PROFILES_DIR=/app/profiles \
    QA_CONTRACTS_DIR=/app/contracts \
    QA_UI_DIR=/app/ui \
    QA_DEMO_DIR=/app/demo \
    QA_WORKERS=1

# Fontes só para gerar o lote de demonstração sintético.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app/engine
COPY engine/pyproject.toml engine/uv.lock engine/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY engine/src ./src
RUN uv sync --frozen --no-dev
COPY contracts /app/contracts
COPY profiles /app/profiles

# Lote de demonstração (faltando, em branco, torta, sem nitidez), gerado e não versionado.
# Se falhar, a imagem sobe sem ele: a interface só esconde o botão.
COPY tools/synth /app/tools/synth
RUN /app/engine/.venv/bin/python /app/tools/synth/synth.py showcase --out /app/demo/lote-demonstracao \
    || echo "aviso: lote de demonstração não gerado"

COPY --from=ui /app/ui/dist /app/ui

RUN useradd --create-home --uid 10001 qa && mkdir -p /data && chown qa /data
USER qa
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % (os.environ.get('QA_PORT') or os.environ.get('PORT') or 8000))"
CMD ["/app/engine/.venv/bin/python", "-m", "qa_engine.entrypoints.http"]
