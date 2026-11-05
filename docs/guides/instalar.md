# Instalar e rodar localmente

## Requisitos

- Python 3.12 ou mais novo e [uv](https://docs.astral.sh/uv/)
- Fontes DejaVu (só para gerar a base sintética): `apt-get install fonts-dejavu-core`
- Docker, para rodar como na nuvem

## Motor e linha de comando

```bash
cd engine
uv sync                       # cria .venv com as versões do uv.lock
uv run qa rules               # lista as regras registradas
uv run qa analyze ../caminho/do/lote --profile ../profiles/demo.yaml --out ../saida
```

A saída tem `report.json` (contrato `analysis.schema.json`), `findings.csv`,
`metadata.csv`, `rework_order.csv` e `metadata/<documento>.json`.

## API

```bash
cd engine
QA_API_TOKEN=troque-isto QA_DATA_DIR=../data uv run python -m qa_engine.entrypoints.http
# http://localhost:8000/docs
```

| Variável | Padrão | Uso |
| --- | --- | --- |
| `QA_API_TOKEN` | vazio (sem autenticação) | Token exigido em `Authorization: Bearer` |
| `QA_CORS_ORIGINS` | vazio | Domínios da interface, separados por vírgula |
| `QA_DATA_DIR` | `./data` | Lotes enviados e banco SQLite |
| `QA_PROFILES_DIR` | `profiles/` do repositório | Perfis YAML |
| `QA_RETENTION_HOURS` | 24 | Lotes mais antigos são apagados |
| `QA_MAX_UPLOAD_MB` | 2048 | Limite do envio |
| `QA_WORKERS` | todos os núcleos | Processos de análise |

## Docker

```bash
docker build -f deploy/Dockerfile -t qa-engine .
docker run -p 8000:8000 -e QA_API_TOKEN=troque-isto qa-engine
```

## Testes e qualidade

```bash
cd engine
uv run pytest                     # inclui a suíte de conformidade (~1 min)
uv run pytest -m "not conformance"
uv run ruff check . && uv run ruff format --check . && uv run mypy
```
