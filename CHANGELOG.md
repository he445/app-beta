# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões
[SemVer](https://semver.org/lang/pt-BR/). Commits seguem
[Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/).

## [Não lançado]

### Adicionado

- "Corrigir tudo" num documento ou no lote inteiro: decide `correct` em todas as
  sinalizações pendentes com correção automática (endireitar, girar, espelhar, recortar
  bordas, brilho e contraste, pontilhado, cinza, remover página em branco, reordenar pela
  numeração). Página faltando, defeitos que exigem redigitalizar e duplicatas ficam
  pendentes, com o motivo. Progresso real, decisões com revisor, horário e
  `operation_id`, e desfazer em lote só do que a operação aplicou (ADR-0009).
- Lote corrigido para baixar: `.zip` com a mesma estrutura de pastas, ordem final,
  removidas fora, versão corrigida mais recente, arquivos renumerados, TIFF Deflate (sem
  perda) com o DPI do original e `manifest.json`/`manifest.csv`. Recusado enquanto houver
  página faltando sem decisão.
- Tela de sequência: faixas "Antes" e "Depois" com marcas do que mudou ("endireitada
  2,3°", "movida da posição 7 para a 6", "removida: em branco", "precisa redigitalizar"),
  tela de carregamento com progresso real, "Salvar correções" e "Desfazer correções";
  cartão de página faltando com três decisões (retrabalho, defeito de origem, aprovar
  mesmo assim); zoom com duplo clique ou Z, alternância Original/Corrigida e teclado.
- "Corrigir o lote inteiro" no painel e na revisão; "Baixar lote corrigido" no relatório.
- Contrato 0.3.0: rotas `bulk-corrections`, `corrected-plan`, `corrected-batch` e os
  esquemas `bulk-correction*`, `corrected-*`; `Decision.operation_id`.
- Especificação `spec/corrections.md` e ADR-0009.

### Alterado

- A versão corrigida de uma página passa a ser o original com **todas** as correções de
  imagem decididas, em ordem canônica; antes, cada correção partia do original e a última
  sobrescrevia as outras. O log `corrections.jsonl` ganhou formato novo (cadeia e versão).
- A decisão individual saiu do `app.py` para o caso de uso `CorrectionService`.

- Interface web (`ui/`): envio de pasta ou `.zip`, progresso ao vivo, painel do lote, fila
  de revisão pelo teclado (A, C, R, O, setas, espaço, Ctrl+Z, 1–4, N) com zoom
  OpenSeadragon e área do defeito destacada, antes e depois da correção, sequência do
  documento com canto da numeração ampliado e reordenação, metadados editáveis, relatório
  e ordem de retrabalho por estação, perfis. Tipos gerados do contrato (ADR-0008).
- Contrato 0.2.0: `DELETE /findings/{id}/decision` e
  `PUT /documents/{id}/metadata/{name}`, com o esquema `metadata-update`.

### Corrigido

- Leituras simultâneas na API compartilhavam a conexão SQLite sem lock e falhavam com
  `InterfaceError` sob carga (miniaturas da interface); teste de regressão incluído.

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
