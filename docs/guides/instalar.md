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
QA_DATA_DIR=../data uv run python -m qa_engine.entrypoints.http
# http://localhost:8000/docs
```

| Variável | Padrão | Uso |
| --- | --- | --- |
| `QA_API_TOKEN` | vazio (sem token) | Liga o token: as rotas da API exigem `Authorization: Bearer` e a interface passa a pedi-lo |
| `QA_CORS_ORIGINS` | vazio | Domínios da interface publicada noutro endereço, separados por vírgula (barra no fim é tolerada) |
| `QA_UI_DIR` | vazio | Interface compilada para servir na mesma origem (na imagem: `/app/ui`) |
| `QA_DEMO_DIR` | vazio | Lotes de demonstração, uma subpasta por lote (na imagem: `/app/demo`) |
| `QA_DATA_DIR` | `./data` | Lotes enviados e banco SQLite |
| `QA_PROFILES_DIR` | `profiles/` do repositório | Perfis YAML |
| `QA_RETENTION_HOURS` | 24 | Lotes mais antigos são apagados |
| `QA_MAX_UPLOAD_MB` | 2048 | Limite do envio |
| `QA_WORKERS` | todos os núcleos (imagem: 1) | Processos de análise; use 1 em servidor de 512 MB |
| `QA_PORT` / `PORT` | 8000 | Porta; `PORT` é a que o Render, o Fly.io e o Cloud Run definem |

Perfis: `profiles/demo.yaml` (padrão da interface) tem foco em página faltando, em branco,
torta e sem nitidez; `profiles/completo.yaml` liga todas as regras.

## Interface na mesma origem, sem Docker

```bash
cd ui && npm ci && VITE_API_URL= npm run build && cd ..
uv run --project engine python tools/synth/synth.py showcase --out demo/lote-demonstracao
cd engine && QA_UI_DIR=../ui/dist QA_DEMO_DIR=../demo QA_WORKERS=1 uv run python -m qa_engine.entrypoints.http
# http://localhost:8000 (também pelo celular na mesma rede: http://<ip-do-computador>:8000)
```

## Docker

```bash
docker build -f deploy/Dockerfile -t qa-digitalizacao .
docker run -p 8000:8000 qa-digitalizacao          # demonstração: só o nome na entrada
docker run -p 8000:8000 -e QA_API_TOKEN=troque-isto qa-digitalizacao   # com token
```

## Testes e qualidade

```bash
cd engine
uv run pytest                     # inclui a suíte de conformidade (~1 min)
uv run pytest -m "not conformance"
uv run ruff check . && uv run ruff format --check . && uv run mypy
```
