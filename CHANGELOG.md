# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões
[SemVer](https://semver.org/lang/pt-BR/). Commits seguem
[Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/).

## [Não lançado]

### Adicionado

- Contrato OpenAPI 3.1 e 17 JSON Schemas 2020-12 (`contracts/`).
- Especificação independente de linguagem: layout do lote, 8 detectores de página,
  sequência e completude, pontuação e veredito, metadados (`spec/`).
- Motor de referência em Python com arquitetura hexagonal (`engine/`):
  - regras `corrupted_file`, `low_resolution`, `blank_page`, `black_borders`, `blur`,
    `skew`, `exposure`, `duplicate_page`, `missing_page`, `out_of_order`,
    `numbering_review` e `completeness_unverifiable`;
  - resolvedor de numeração de folhas por programação dinâmica (lida, inferida,
    renumerada, ambígua, ilegível, ausente; modos simples e frente e verso);
  - estados do documento, veredito do lote e amostragem determinística dos verdes;
  - metadados do Decreto 10.278/2020 (Anexo II) e técnicos (Anexo I);
  - correções automáticas aplicadas em cópia, com log e reanálise;
  - exportação de relatório JSON, CSV de sinalizações, CSV de metadados, JSON por
    documento e ordem de retrabalho por estação.
- API HTTP (FastAPI) com token, CORS, retenção de 24 h, SSE de progresso, decisões,
  correção de numeração e perfis; armazenamento SQLite com migrações em SQL puro.
- Linha de comando `qa` (`analyze`, `rules`, `validate-profile`, `validate-report`).
- Gerador da base sintética com gabarito e medidor de taxa de acerto (`tools/synth/`).
- Suíte de conformidade com gabarito versionado e tolerâncias (`conformance/`).
- Documentação MkDocs: ADD, ADRs 0001–0007, C4 em Mermaid, guias, glossário.
- Dockerfile do motor e integração contínua (lint, tipos, testes, conformidade,
  Spectral, oasdiff, build da documentação e da imagem).
