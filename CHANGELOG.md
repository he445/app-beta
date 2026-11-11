# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões
[SemVer](https://semver.org/lang/pt-BR/). Commits seguem
[Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/).

## [Não lançado]

### Adicionado

- Tela de Configurações no programa desktop (capacidade `settings`): aba
  **Digitalizadoras** com cada regra por perfil e estação, a origem de cada valor e
  "voltar ao herdado"; aba **Este computador** com pastas, estação padrão, recursos e log.
  Valor inválido é recusado antes de salvar. `GET`/`PUT /settings` (422 com `problems`
  por chave), `GET /profiles/{id}/rules` (contrato 0.8.0).
- Parâmetros de regra são conferidos pelo tipo e pela faixa do manifesto (antes só o nome).
- Programa desktop (ADR-0011): `python -m qa_engine.entrypoints.desktop` abre o motor em
  `127.0.0.1` numa porta livre, com token novo a cada abertura, e a interface numa janela
  pywebview; o token vai pela ponte da janela. Uma instância por usuário (a segunda
  abertura traz a janela existente). Sem WebView2, abre no navegador com código de uso
  único (`POST /session/exchange`, contrato 0.7.0). Checagem do cabeçalho `Host`. Log em
  arquivo com rotação e caminhos mascarados; arquivo de queda. `--headless`, `--browser`,
  `--set chave=valor`. Fluxo de ponta a ponta no CI (`ui/e2e/desktop.cjs`).
- `GET /health` informa `mode` (`cloud`, `desktop`, `server`) e `capabilities`;
  `GET /session` devolve o usuário do sistema como revisor no programa desktop
  (contrato 0.6.0). A interface decide o que mostrar pelas capacidades: "Abrir lote" com
  caminho da pasta e estação, "Salvar na pasta de saída", sem tela de entrada quando o
  revisor vem do sistema. O mesmo build serve todos os modos.
- Lote local lido no lugar (ADR-0013): `POST /local-batches` (só no programa desktop),
  raízes permitidas (`allowed_roots`), espera até a pasta parar de mudar, retrato com
  SHA-256 antes da análise e conferência antes de gravar (409 se o original mudou),
  caminhos longos e de rede no Windows (`\\?\`). Estado do lote com `source` e `stage`.
  Contrato 0.5.0. Porta `BatchFolder`, adaptador `LocalFolderSource`, migração 0003.
- Lote corrigido em pasta (`destination: folder`): `output_dir/<lote>-corrigido-<data-hora>`,
  gravado numa pasta temporária e renomeado só no fim (`FolderTiffWriter`). O lote
  corrigido (pasta ou zip) passa a levar `report.json`, `findings.csv` e `decisions.csv`.
- Configuração em camadas (ADR-0012): padrões, arquivo da máquina, arquivo do usuário,
  variáveis `QA_*` e argumentos, validada contra `contracts/schemas/settings.schema.json`.
  Chaves novas: `output_dir`, `temp_dir`, `allowed_roots`, `default_station`,
  `batch_settle_seconds`, `retention_days`, `max_memory_mb` e `log_level`. O arquivo da
  máquina pode travar chaves. Configuração inválida para o programa com a chave, a origem
  e o valor esperado. Porta `SettingsSource`, adaptadores `LayeredSettings` e `AppPaths`.
- `docs/referencia/configuracao.md`, gerada do esquema.
- Ajustes da digitalizadora por estação: `stations[].id` e `stations[].overrides` no
  perfil (`enabled` e `params` por regra), aplicados depois de `detectors`. Cada página é
  julgada com os parâmetros da sua estação; `page.station_id` no relatório. Estação padrão
  do computador para arquivos sem equipamento. Perfil `sos-piloto`.
- Cada lote grava a cópia do perfil efetivo (`profile.json`); decisões e reanálises usam
  essa cópia.
- A suíte de conformidade roda com `completo`, `demo` e `sos-piloto`.
- `tools/docs/gen_reference.py` gera `docs/referencia/api.md`, `perfis.md` e `cli.md` do
  contrato, dos manifestos e do analisador de argumentos.
- `tools/docs/check_docs.py` e lint de Markdown na CI: link relativo quebrado,
  referência gerada desatualizada ou documentação fora de `docs/` reprovam o build.
- Demonstração no celular (ADR-0010): o motor serve a interface na mesma origem
  (`QA_UI_DIR`); lote de demonstração pronto no servidor (`QA_DEMO_DIR`,
  `tools/synth showcase`, rotas `GET /demo-batches` e `POST /demo-batches/{name}`); tela
  de partida que espera o motor acordar; botão "Ampliar" nas miniaturas; escolha de
  imagens no celular; roteiro `ui/e2e/celular.cjs` (Pixel 7 e iPhone 13) na CI.
- Perfil `completo` (todas as regras), usado pela conformidade e pelas métricas.
- `GET /health` informa `auth_required` e `demo_batches` (contrato 0.4.0).
- Caso de conformidade "lacuna grande no fim do documento".

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
- Especificação `docs/especificacoes/corrections.md` e ADR-0009.

### Alterado

- `corrupted_file` 1.1.0: arquivo bloqueado por outro programa, sem permissão ou em rede
  que caiu vira "arquivo inacessível", com a correção "abrir o lote de novo".
- `workers` automático passa a ser núcleos − 1 (mínimo 1), limitado pelo teto de memória
  (`max_memory_mb`); antes eram todos os núcleos.
- Documentação reorganizada numa pasta só, em português (ADR-0017): `spec/` virou
  `docs/especificacoes/`, `docs/guides` virou `docs/guias`, `docs/architecture` virou
  `docs/arquitetura` (agora no formato arc42), `docs/reference` virou `docs/referencia` e
  os `README.md` das pastas viraram páginas de `docs/`. Páginas novas: visão geral,
  princípios, casos de borda, operação, modelos, segurança e privacidade, licenças de
  terceiros e testes. O `README.md` da raiz ficou curto e aponta para `docs/`.
- Os manifestos das regras e `detector-manifest.schema.json` apontam para
  `docs/especificacoes/`.
- Entrada só com o nome do revisor; o token fica dormente e aparece quando o motor
  exige (`QA_API_TOKEN`).
- Perfil `demo` com foco em página faltando, em branco, torta e sem nitidez; bordas
  pretas, exposição, resolução e duplicata desligadas (o código continua).
- Imagem Docker única (interface + motor + lote de demonstração), com `QA_WORKERS=1`; o
  servidor aceita a porta de `PORT`.
- Barra de navegação em duas linhas e alvos de toque de 44 px no celular.

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

- A retenção apagava a pasta `root` do lote; agora apaga só a pasta de trabalho em
  `data_dir`, e a pasta de origem nunca é tocada.
- "Failed to fetch" no celular: respostas 401 e 500 sem cabeçalho CORS; origem
  configurada com barra no fim bloqueava tudo; endereço do motor gravado no aparelho
  sobrepunha o da publicação; motor dormindo no plano gratuito; processos de análise
  demais para 512 MB.
- Resolvedor de numeração: lacuna grande no fim do documento era tomada por leitura
  errada; agora vira página faltando (teto `w_gap_max`, `docs/especificacoes/sequencing.md` 1.1.0).
- Telas estreitas: faixas de miniaturas alargavam a página inteira.

- Leituras simultâneas na API compartilhavam a conexão SQLite sem lock e falhavam com
  `InterfaceError` sob carga (miniaturas da interface); teste de regressão incluído.

- Contrato OpenAPI 3.1 e 17 JSON Schemas 2020-12 (`contracts/`).
- Especificação independente de linguagem: layout do lote, 8 detectores de página,
  sequência e completude, pontuação e veredito, metadados (`docs/especificacoes/`).
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
- Documentação MkDocs: ADRs 0001–0007, C4 em Mermaid, guias, glossário.
- Dockerfile do motor e integração contínua (lint, tipos, testes, conformidade,
  Spectral, oasdiff, build da documentação e da imagem).
