# Interface web

Site estático (React + TypeScript + Vite) que fala com o motor só pela API de
[`contracts/openapi.yaml`](../contracts/openapi.yaml). Nada é instalado nos computadores:
basta o navegador (ADR-0001).

## Rodar

```bash
# 1. motor
cd engine && QA_API_TOKEN=demo-token uv run python -m qa_engine.entrypoints.http
# 2. interface (outra aba); /api é encaminhado para localhost:8000
cd ui && npm ci && npm run dev        # http://localhost:5173
```

Entre com seu nome (gravado em cada decisão) e o token. Para publicar como site estático:

```bash
VITE_API_URL=https://motor.exemplo npm run build   # gera dist/
```

e configure `QA_CORS_ORIGINS` no motor com o domínio do site.

## Telas (seção 12 do ADD)

| # | Tela | Rota |
| --- | --- | --- |
| 1 | Enviar lote (pasta arrastada ou `.zip`, perfil, manifesto, numeração) | `#/` |
| 2 | Processamento ao vivo (SSE) | `#/batches/<id>` |
| 3 | Painel do lote | `#/batches/<id>` |
| 4–5 | Fila de revisão e detalhe da página, pelo teclado | `#/batches/<id>/review` |
| 6 | Sequência do documento: "Corrigir tudo", faixas Antes/Depois, página faltando, zoom | `#/batches/<id>/sequence/<doc>` |
| 7 | Metadados editáveis | `#/batches/<id>/metadata/<doc>` |
| 8 | Relatório e ordem de retrabalho | `#/batches/<id>/reports` |
| 9 | Perfis | `#/profiles` |

Na sequência: clique numa página (ou Enter) para corrigir a numeração; duplo clique (ou
**Z**) amplia, com **← →** para passar de página e **Esc** para fechar.

Atalhos da revisão: **A** aprovar, **C** corrigir, **R** retrabalho, **O** defeito de
origem, **← →** navegar, **Espaço** ampliar, **Ctrl+Z** desfazer, **1–4** filtrar por
severidade, **N** digitar a numeração.

## Estrutura

```text
src/api/schema.d.ts   tipos gerados do contrato (npm run gen; não editar)
src/api/              cliente HTTP, SSE via fetch, hooks do TanStack Query
src/lib/              lógica pura e testada: fila, atalhos, CSV, arquivos arrastados
src/components/       visualizador OpenSeadragon, miniaturas, emblemas
src/screens/          uma tela por arquivo
e2e/                  fluxo completo no navegador (Playwright)
```

## Verificações

```bash
npm run gen && git diff --exit-code src/api/schema.d.ts   # tipos em dia com o contrato
npm run typecheck && npm test && npm run build
node e2e/fluxo-completo.cjs ../lote-demo.zip /tmp/capturas  # com motor e vite no ar
```

O fluxo completo envia um `.zip`, espera o painel, decide pelo teclado e desfaz, aplica uma
correção automática, roda "Corrigir tudo" num documento e "Corrigir o lote inteiro" lendo
a tela de carregamento, confere as faixas Antes/Depois, decide a página faltando (com o
Salvar bloqueado até lá), abre o zoom por duplo clique e pelo teclado, salva e inspeciona
o zip (TIFF Deflate e manifesto), edita um metadado, baixa a ordem de retrabalho e confere
que não há erro de console nem rolagem horizontal no celular. Com o terceiro argumento
(pasta do lote original), confere também que nenhum arquivo original mudou.
