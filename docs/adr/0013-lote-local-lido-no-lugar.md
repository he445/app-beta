# 0013: Lote local lido no lugar, com retrato antes e depois

Status: aceito · Data: 2026-11-11 · Decisores: Everton Ferreira

## Contexto

No programa desktop o lote está numa pasta onde a digitalizadora grava, no próprio
computador ou num compartilhamento da rede interna (`\\servidor\pasta`). O motor em
servidor recebia o lote por envio e trabalhava numa cópia. Numa estação, copiar dobra o
disco e o tempo, principalmente em pasta de rede. Por outro lado, ler no lugar abre três
riscos: analisar enquanto a digitalizadora ainda grava, a pasta mudar durante a revisão
e, por engano, apagar o original.

## Opções consideradas

1. Copiar o lote para a pasta do programa antes de analisar.
2. Ler no lugar, só para leitura, com espera de estabilidade, retrato e raízes
   permitidas.

## Decisão

Opção 2.

- **Leitura no lugar.** Nada é escrito na pasta original. A pasta de trabalho do lote
  fica em `data_dir`.
- **Espera de estabilidade.** O lote só é analisado depois de `batch_settle_seconds`
  sem nenhum arquivo novo, apagado ou alterado.
- **Retrato.** Tamanho, data e SHA-256 de cada arquivo antes da análise. Antes de gravar
  o lote corrigido, a pasta é comparada de novo; se algo mudou, a gravação é recusada
  (409) com a lista do que mudou.
- **Raízes permitidas.** `allowed_roots` limita de onde se abre lote; a TI pode travar
  essa chave no arquivo da máquina (ADR-0012).
- **Caminho longo e UNC.** No Windows o caminho é convertido para a forma estendida
  (`\\?\`, `\\?\UNC\`), sem exigir `LongPathsEnabled`.
- **Arquivo inacessível não derruba o lote.** Vira uma sinalização na página.
- **Porta `BatchFolder`**, adaptador `LocalFolderSource`.
- **Saída em pasta.** O lote corrigido pode ir para `output_dir`, gravado numa pasta
  temporária oculta e renomeado só no fim (`FolderTiffWriter`). O zip continua.
- A retenção apaga só a pasta de trabalho do lote, nunca a pasta de origem; antes ela
  apagava a pasta do lote enviado, o que num lote local seria o original.

## Consequências

- O SHA-256 é calculado duas vezes por arquivo (retrato e metadados). Em pasta de rede
  lenta, isso pesa; se a medição na estação mostrar que estoura o orçamento, o retrato
  passa a reaproveitar o SHA-256 da análise.
- Contrato 0.5.0: `POST /local-batches`, `source` e `stage` no estado do lote,
  `destination` no pedido do lote corrigido.
- Migração `0003_local_batches.sql`.
