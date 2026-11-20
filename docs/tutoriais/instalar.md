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

As variáveis mais usadas (todas as chaves em [Configuração](../referencia/configuracao.md);
camadas e arquivos em [Configurar este computador](../guias/configurar-computador.md)):

| Variável | Padrão | Uso |
| --- | --- | --- |
| `QA_API_TOKEN` | vazio (sem token) | Liga o token: as rotas da API exigem `Authorization: Bearer` e a interface passa a pedi-lo |
| `QA_CORS_ORIGINS` | vazio | Domínios da interface publicada noutro endereço, separados por vírgula (barra no fim é tolerada) |
| `QA_UI_DIR` | vazio | Interface compilada para servir na mesma origem (na imagem: `/app/ui`) |
| `QA_DEMO_DIR` | vazio | Lotes de demonstração, uma subpasta por lote (na imagem: `/app/demo`) |
| `QA_DATA_DIR` | `./data` | Lotes enviados e banco SQLite |
| `QA_PROFILES_DIR` | `profiles/` do repositório | Perfis YAML |
| `QA_RETENTION_HOURS` ou `QA_RETENTION_DAYS` | 24 h | Lotes mais antigos são apagados |
| `QA_MAX_UPLOAD_MB` | 2048 | Limite do envio |
| `QA_WORKERS` | núcleos − 1 (imagem: 1) | Processos de análise; use 1 em servidor de 512 MB |
| `QA_PORT` / `PORT` | 8000 | Porta; `PORT` é a que o Render, o Fly.io e o Cloud Run definem |

Perfis: `profiles/demo.yaml` (padrão da interface) tem foco em página faltando, em branco,
torta e sem nitidez; `profiles/completo.yaml` liga todas as regras.

## Desenvolvimento: motor e interface com recarga automática

Dois terminais: o motor serve a API e a interface roda no Vite, que recarrega a cada
mudança no código e encaminha `/api` para o motor (sem CORS).

```bash
# Terminal 1: motor, API em http://localhost:8000 (documentação em /docs)
cd engine
uv sync
uv run python -m qa_engine.entrypoints.http

# Terminal 2: interface em http://localhost:5173
cd ui
npm ci
npm run dev
```

No Windows (PowerShell) os comandos são os mesmos, um por linha ou separados por `;`.

- **Dados:** lotes e banco SQLite ficam em `engine/data` (o padrão `./data` vale a partir
  da pasta onde o motor foi aberto). Para começar com o banco vazio, pare o motor e mova
  ou apague essa pasta; ele cria outra ao abrir.
- **Mudança no motor** pede reiniciar o motor (Ctrl+C e o mesmo comando). Mudança na
  interface aparece sozinha.
- **Motor noutra porta ou máquina:** `QA_ENGINE_URL=http://outra:8000 npm run dev`.
- **Modelos de leitura da numeração e da orientação:** no modo servidor o motor abre sem
  eles. Para usá-los, baixe uma vez (`uv run --project engine python tools/models/fetch.py
  --out models`, na raiz do repositório) e abra o motor com `QA_MODELS_DIR=../models`.
- **`uv` não encontrado no Windows:** instalado com `pip install --user uv`, ele fica em
  `%APPDATA%\Python\Python3XX\Scripts`, fora do PATH. Acrescente essa pasta ao PATH ou
  use `python -m uv` no lugar de `uv`.
- **Fontes DejaVu no Windows** (base sintética e parte dos testes): baixe o pacote
  `dejavu-fonts-ttf` e aponte `QA_SYNTH_FONT_DIR` para a pasta `ttf` dele.
- **Tipos da interface:** depois de mudar `contracts/`, rode `npm run gen` em `ui/`.

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
