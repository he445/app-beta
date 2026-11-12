# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões
[SemVer](https://semver.org/lang/pt-BR/). Commits seguem
[Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/).

## [Não lançado]

### Adicionado

- Manual do conferente (`docs/operacao/manual-do-conferente.md`): a caixa de exemplo do
  pacote conferida do começo ao fim. Tela de atalhos de teclado em qualquer tela (tecla
  **?** ou "Atalhos (?)" no topo), com os atalhos da revisão, da sequência e da página
  ampliada. O CI segue o manual na caixa de exemplo (`e2e/manual.cjs`).
- Voltar versão: antes de aplicar migrações novas, o banco é copiado para
  `backups/antes-de-atualizar`; uma versão anterior não abre banco de versão mais nova e
  diz como restaurar (`qa backup restore --before-update`); guia de atualizar e voltar
  versão. A versão de cada máquina aparece na Gestão.
- Metadados do Decreto no lote corrigido: tags descritivas do original preservadas no
  TIFF, `Software` e `DateTime` registrando a correção e qual, XMP com os campos do
  Decreto e a origem de cada valor; `metadados.json` por processo com os campos e o
  SHA-256 de cada arquivo entregue (`process-metadata.schema.json`).
- Backup do banco local: cópia consistente (API de backup do SQLite) ao abrir, uma vez
  por dia e ao fechar, para `backup_dir/<máquina>` (nova chave) ou `backups` na pasta de
  dados, guardando as 14 mais novas; `qa backup list|now|restore` (também pelo
  `QA-suporte.exe`), com conferência da cópia, programa fechado e o banco anterior
  guardado.
- Trava por caixa: abrir o lote trava as caixas em `reports_dir/travas` (ou só nesta
  máquina, com aviso); outra máquina vê quem está com a caixa, em qual máquina e desde
  quando; renovação a cada minuto pela tela; trava abandonada (10 minutos) pode ser
  assumida, com registro (migração 0011); fechar o programa solta as travas.
  `/batches/{id}/lock` (contrato 0.18.0).
- Permissões e histórico de configuração: perfis e ajustes das digitalizadoras só com o
  token de administrador fora da demonstração (403 sem token configurado); campos
  bloqueados na tela até destravar; toda mudança (perfil e este computador) entra no
  histórico com quem, quando, antes e depois (`GET /config-history`, migração 0010),
  mostrado em Configurações e gravado no resumo de configuração de cada lote
  (`configuracao.json`, também no lote corrigido). Contrato 0.17.0.
- Folha inserida depois: arrastar o arquivo para a Sequência (no ponto certo ou em
  "Adicionar folha") guarda a folha na área de complementos do lote (nunca na pasta
  original), analisa com a linha de base do lote, lê o número, sugere a posição por ele,
  resolve a sequência de novo (a lacuna fecha) e gera versão nova do relatório da caixa;
  remover desfaz, com auditoria (contrato 0.16.0, migração 0009).
- Liberação por processo (ADR-0018): cada processo fica pronto para conferir assim que é
  analisado (relatório parcial com a mediana do que já foi analisado, sem duplicata);
  fila no painel (pronto, analisando, na fila) e evento `document_ready`; passada final
  com a duplicata, mesclada sem perder decisões, numeração digitada nem ordem manual, e
  "reavaliar" no processo já conferido que ganhou achado novo. Corrigir tudo, salvar e
  relatório por caixa esperam a passada final (contrato 0.15.0, migração 0008).
- Leitor de numeração: alternativa com 1 e 7 trocados (metade da confiança) para o
  resolvedor decidir pela sequência; corrige o cenário de intercalação no Windows.
- Tela de Gestão: lê os relatórios por caixa de `reports_dir` (todas as máquinas) ou, sem
  ela, os deste computador; por conferente → caixas → processos, estado da pendência,
  filtro por dia, semana ou mês com totais, PDF do relatório e versão do programa em
  cada máquina. Sem tempo por caixa nem ranking. `GET /management` e
  `/management/report.pdf` (contrato 0.14.0, `management.schema.json`).
- Relatório por caixa: ao salvar (ou sob pedido), cada caixa concluída gera o relatório
  com páginas faltando e ilegíveis de cada processo, ou "Nenhuma pendência", em JSON
  (`box-report.schema.json`) e PDF (ReportLab, BSD-3-Clause, no ADR-0004), na pasta de
  saída e em `reports_dir` (nova chave, para a Gestão). Versão nova só quando as
  pendências mudam; as anteriores ficam guardadas (migração 0007). Rotas
  `/batches/{id}/box-reports` e `/box-reports/{id}.pdf` (contrato 0.13.0); cartão na tela
  de Relatório; o teste de fumaça do pacote confere o PDF.
- Folha em branco depende da numeração (`blank_page` 1.1.0): folha com numeração (do
  `numbering.json` ou qualquer escrito na região, inclusive riscado) nunca é branca; em
  página quase vazia, com os modelos, o leitor procura escrito nos quatro cantos. Os
  cinco casos sintéticos em `tools/synth/numbering.py brancas`.
- Coleta do beta (porta `FeedbackStore`, adaptador `SqliteFeedbackStore`): numeração
  digitada e decisão de orientação do garantidor viram exemplo rotulado só nesta máquina
  (recorte ou miniatura, rótulo e o que o modelo disse), com retenção por perfil
  (`feedback.enabled`, `feedback.retention_days`; ligada no perfil do piloto).
  `qa feedback export` gera o pacote para o ajuste fino; `qa beta report` calcula as
  métricas do piloto do banco local (`beta-report.schema.json`), com as contagens de cada
  lote guardadas antes da retenção (migração 0006). `QA-suporte.exe` atende os comandos
  `admin`, `beta`, `feedback`, `rules` e `validate-*`.
- Tela de Sequência: digitação rápida embaixo de cada página (Enter grava e vai para a
  próxima com dúvida, Tab passa, Esc volta; gravações em fila), recorte da região onde a
  numeração foi lida, arrastar e Alt + setas para reordenar (ordem do revisor no lote
  corrigido), **Voltar à ordem do arquivo** e **Desfazer**/Ctrl+Z. Roteiro desktop
  resolve um documento de três folhas sem número só no teclado
  (`tools/synth/numbering.py sequencia`).
- Tela de Sequência, motor: `PUT /batches/{id}/documents/{doc}/numbering` (caso de uso
  `set_manual_numbering`) grava numeração digitada (`null` desfaz) e ordem escolhida pelo
  revisor (`manual_order`, com revisor e horário; `null` desfaz), valida tudo antes de
  gravar e devolve o documento com estado, ordem e lacunas recalculados. A ordem manual
  vale no lote corrigido (contrato 0.12.0, migração 0005).
- Numeração lida da imagem (ADR-0015): sem `numbering.json` no lote, a análise procura o
  número de folha escrito à mão no canto da página já de pé (detector PP-OCRv5 com plano
  B por componentes conexos, separação de números lado a lado, riscado por geometria e
  reconhecedor PP-OCRv5 restrito ao vocabulário de folha; TrOCR como alternativa). Perfil
  `numbering`: `regions`, `struck_threshold`, `recognizer`, `min_height_mm`,
  `read_from_image`. Relatório com `numbering.source`, `numbering.marks` (o que foi lido)
  e `numbering.typed` (o que o revisor digitou); re-resolução usa as marcas gravadas;
  recorte da região em `GET /pages/{id}/numbering-crop` (contrato 0.11.0).
- Numeração manuscrita sintética (`tools/synth/numbering.py`): oito cenários do leitor por
  imagem e recortes rotulados, com fontes manuscritas OFL versionadas; bench dos
  reconhecedores (`tools/bench_numbering.py`: acerto exato, entre as três leituras,
  ambíguo e tempo).
- Rotação na revisão: botões e atalhos Q, E e W giram a cópia da página (somando ao giro
  já aplicado); cada giro é decisão auditada numa sinalização `orientation` (a do modelo
  ou uma nova) e vai para o lote corrigido. `PUT /pages/{id}/rotation` (contrato 0.10.0).
  Miniaturas da fila mostram a cópia corrigida.
- Orientação da página (ADR-0014): regra `orientation` com o classificador
  PP-LCNet_x1_0_doc_ori (porta `OrientationClassifier`); rotação automática acima de 0,90
  e sugerida para revisão entre 0,60 e 0,90 (fora do "Corrigir tudo"); inclinação medida
  numa vista girada em memória; página quase branca não é classificada. Base sintética com
  páginas giradas, com pouco texto e só com carimbo; conformidade com os modelos.
  `qa analyze --models`.
- Diagnóstico (ADR-0016): erros do motor, dos trabalhos de fundo, da abertura e da
  interface (error boundary, `window.onerror`, promessas rejeitadas), sem imagem nem texto
  de documento e com caminhos mascarados; agrupamento por assinatura; pasta compartilhada
  (`diagnostics_dir`); `qa admin token` (hash scrypt só no arquivo da máquina); rotas
  `/admin/diagnostics/*` com `X-Admin-Token` e bloqueio após cinco erros; tela com
  cartões, gráfico por dia, filtros, detalhe, resolver e exportar pacote (contrato 0.9.0,
  migração 0004).
- Modelos embarcados: `models.lock.json` (orientação PP-LCNet_x1_0_doc_ori, detector
  PP-OCRv5_mobile_det, reconhecedores trocr-small-handwritten e PP-OCRv5_mobile_rec, com
  origem fixada por commit, licença e SHA-256), `tools/models/fetch.py` (download só no
  build), conferência ao abrir com bloqueio da análise (503) e `models` em `/health`,
  chave `models_dir`, adaptador `OnnxRuntimeModel` (uma sessão e uma thread por
  processo). Dependências `onnxruntime` (MIT) e `tokenizers` (Apache-2.0). Fichas dos
  modelos em `docs/modelos/`.
- Build Windows (`deploy/windows/`): spec do PyInstaller em modo pasta com `QA.exe`
  (janela) e `QA-suporte.exe` (console), script `build.ps1`, workflow em `windows-latest`
  com testes e conformidade em Windows, teste de fumaça e zip com SHA-256.
  `--self-test` analisa o lote de exemplo do pacote (`tools/synth selftest`), confere o
  gabarito e mede o custo por página. `QA_SYNTH_FONT_DIR` para gerar lotes fora do Linux.
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

- `skew` e `blur` 1.1.0: página quase branca (cobertura abaixo de 0,01) não é avaliada.
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

- A versão corrigida de uma página era reaproveitada comparando só as sinalizações da
  cadeia; agora compara também ação e parâmetros.
- Windows: a segunda abertura do programa não conseguia ler a porta da primeira (o
  trecho travado do arquivo não pode ser lido por outro processo); porta e segredo agora
  ficam em `instance.json`, separado da trava.
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
