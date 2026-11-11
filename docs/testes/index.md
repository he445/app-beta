# Testes

## Estratégia

| Camada | O que cobre | Onde |
| --- | --- | --- |
| Unidade | Detectores, resolvedor de sequência, pontuação, correções | `engine/tests/test_detectors.py`, `test_sequencing.py`, `test_scoring.py` |
| Propriedade | Invariantes do resolvedor e da pontuação com entradas geradas (Hypothesis) | os mesmos arquivos |
| Aplicação | Análise de ponta a ponta, "Corrigir tudo", desfazer, lote corrigido | `test_pipeline.py`, `test_bulk_corrections.py` |
| API | Rotas, erros RFC 9457, token, CORS | `test_api.py`, `test_http_access.py` |
| Contrato | Esquemas válidos, manifestos e perfis contra o contrato | `test_contracts.py`, Spectral e oasdiff na CI |
| Arquitetura | A dependência aponta para dentro | `test_architecture.py` |
| Documentação | Toda regra tem especificação e caso de conformidade; links; referência gerada em dia | `test_documentation.py`, `tools/docs/check_docs.py` |
| Conformidade | O lote `core` gerado tem de casar com o gabarito versionado | [Suíte de conformidade](conformidade.md) |
| Interface | Funções puras (fila, atalhos, correções) e cliente HTTP | `ui/src/**/*.test.ts` (Vitest) |
| Ponta a ponta | Fluxo completo no navegador, no celular e no programa desktop sem janela | `ui/e2e/` (Playwright) |
| Pacote Windows | Testes e conformidade em Windows; teste de fumaça do executável com o lote de exemplo e custo por página | `.github/workflows/windows.yml`, `QA-suporte.exe --self-test` |

## Como rodar

```bash
cd engine
uv run pytest                       # tudo, com a suíte de conformidade (~1 min)
uv run pytest -m "not conformance"  # rápido
uv run ruff check . ../tools ../conformance && uv run ruff format --check . ../tools ../conformance
uv run mypy

cd ../ui
npm ci && npm run typecheck && npm test

cd ..
uv run --project engine python tools/docs/check_docs.py   # checagens da documentação
```

## Metas e resultado atual

Medidas na [base sintética](base-sintetica.md) com o perfil `completo`; o passo a passo e
os números obtidos estão em [Demonstração](../guias/demonstracao.md).

| Métrica | Meta |
| --- | --- |
| Defeitos críticos encontrados | 98% ou mais |
| Todos os defeitos encontrados | 95% ou mais |
| Sinalizações corretas (precisão) | 70% ou mais |
| Páginas que dispensam revisão humana | 50% ou mais |
| Página faltando encontrada, quando há numeração | 95% ou mais |
| Velocidade em 4 núcleos, sem GPU | 3 páginas por segundo ou mais |

Precisão de 70% é aceitável porque um falso positivo custa cerca de 1 segundo de revisão,
e um falso negativo custa um documento errado entregue. Por isso encontrar vem antes de
acertar.
