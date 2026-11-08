# QA Automático de Digitalização — PoC

Triagem automática de lotes digitalizados: detecta defeitos de imagem, de sequência e de
completude, propõe uma correção para cada um, extrai os metadados do Decreto 10.278/2020
e entrega ao revisor só o que precisa de olho humano.

O desenho completo está no [ADD](docs/add.md). Este repositório segue os sete princípios
dele: o original é intocável, o humano decide, toda detecção explica a si mesma, limiar é
configuração, contrato e especificação vêm antes do código, e sem documentação não está
pronto.

## Começo rápido

```bash
cd engine && uv sync && cd ..
uv run --project engine python tools/synth/synth.py demo --out lote-demo --pages 200
uv run --project engine qa analyze lote-demo --profile profiles/demo.yaml --out saida
uv run --project engine python tools/synth/evaluate.py saida/report.json lote-demo/gabarito.json
```

Para revisar pela interface web (detalhes em [ui/README.md](ui/README.md)):

```bash
(cd engine && QA_API_TOKEN=demo-token uv run python -m qa_engine.entrypoints.http) &
cd ui && npm ci && npm run dev    # http://localhost:5173, token demo-token
```

Na tela de sequência, **Corrigir tudo** aplica as correções automáticas (endireitar,
recortar bordas, remover página em branco, reordenar pela numeração), mostra o antes e o
depois e **Salvar correções** baixa o lote corrigido em `.zip` (TIFF sem perda, mesma
estrutura de pastas e manifesto). Detalhes em [spec/corrections.md](spec/corrections.md).

Na base sintética de referência (199 páginas A4 a 300 dpi, 4 núcleos, sem GPU): 100% dos
defeitos críticos encontrados, precisão de 88,7%, 67% das páginas dispensam revisão,
cerca de 7 páginas por segundo. Detalhes e ressalvas em
[docs/guides/demonstracao.md](docs/guides/demonstracao.md).

## Estrutura

```text
contracts/      fonte da verdade: OpenAPI 3.1 + JSON Schema 2020-12
spec/           especificação independente de linguagem (detectores, sequência, pontuação)
conformance/    gabarito, tolerâncias e executor que qualquer implementação precisa passar
engine/         implementação de referência em Python (domain, detectors, application,
                ports, adapters, entrypoints/http e cli)
ui/             interface web (React + TypeScript + Vite), tipos gerados do contrato
profiles/       perfis de cliente (limiares e regras como configuração)
tools/synth/    gerador da base sintética e medidor de taxa de acerto
deploy/         Dockerfile do motor
docs/           site MkDocs: ADD, guias, ADRs, C4, referência, glossário
```

## Regras implementadas

| Regra | Severidade | Correção proposta |
| --- | --- | --- |
| `corrupted_file` | crítico | regerar ou redigitalizar |
| `blur` | crítico | redigitalizar |
| `missing_page` | crítico | localizar a folha (ou o verso) e redigitalizar |
| `low_resolution` | alto | reconfigurar o scanner e redigitalizar |
| `exposure` | alto | auto-níveis na cópia ou redigitalizar |
| `numbering_review` | alto/médio | revisor digita a numeração (tecla N) |
| `skew` | médio (alto > 3°) | endireitar na cópia |
| `out_of_order` | médio | reordenar pela numeração |
| `duplicate_page` | médio | remover a cópia de pior qualidade |
| `blank_page` | baixo | remover conforme o perfil (quase branca nunca é removida) |
| `black_borders` | baixo | recortar na cópia |
| `completeness_unverifiable` | baixo | incluir contagem no manifesto |

`uv run --project engine qa rules` lista versões e títulos.

## Documentação

```bash
uvx --with mkdocs-material --with mkdocstrings-python --with pymdown-extensions mkdocs serve
```

- [Instalar e rodar](docs/guides/instalar.md) · [Demonstração](docs/guides/demonstracao.md)
- [Arquitetura (C4)](docs/architecture/c4.md) · [ADRs](docs/adr/)
- [Criar um detector](docs/guides/criar-detector.md) · [Portar para outra linguagem](docs/guides/portar-linguagem.md)
- [Contribuir](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [Glossário](docs/glossary.md)

## Dados

Só documentos sintéticos, públicos ou próprios. **Nenhum documento de cliente** antes de
autorização formal; no piloto, o motor roda em servidor interno (ADR-0001).
