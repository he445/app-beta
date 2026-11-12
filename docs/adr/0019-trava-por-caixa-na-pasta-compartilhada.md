# 0019: Trava por caixa em arquivo na pasta compartilhada de relatórios

Status: aceito · Data: 2026-11-12 · Decisores: Everton Ferreira

## Contexto

Cada estação tem o próprio banco SQLite e lê a caixa direto da pasta da digitalizadora,
só para leitura. Dois conferentes podem abrir a mesma caixa em máquinas diferentes sem
saber, e cada um decide numa cópia separada. Não há servidor central no piloto; a pasta
compartilhada de relatórios (`reports_dir`) já é vista por todas as máquinas.

## Opções consideradas

1. Arquivo de trava ao lado das imagens: a pasta original é só leitura e não pode
   ganhar arquivo nenhum (ADR-0013).
2. Trava do sistema de arquivos (lock de SMB) aberta enquanto a caixa está aberta: cai
   junto com a conexão de rede, não diz quem está com a caixa nem desde quando, e uma
   trava presa depende da TI para soltar.
3. Arquivo JSON por caixa na pasta compartilhada de relatórios, renovado a cada minuto,
   com abandono depois de dez minutos sem renovação.
4. Servidor de travas: é o servidor interno, fase seguinte.

## Decisão

Opção 3 ([especificação](../especificacoes/trava-por-caixa.md)).

- Porta `BoxLockStore` com o adaptador `FolderBoxLocks`: criação exclusiva, renovação e
  posse gravadas num temporário e renomeadas; histórico em `historico.jsonl`.
- Caso de uso `BoxLocks`: trava as caixas ao abrir o lote, renova numa thread a cada
  minuto, solta quando a caixa é concluída. Trava viva nunca é assumida; abandonada só
  com pedido explícito, e o fato fica registrado.
- Sem pasta compartilhada, ou com ela fora do ar, a trava vai para `data_dir/travas` e
  vale só neste computador; a tela avisa. A renovação a leva para a pasta compartilhada
  quando ela volta.
- Fechar o programa não solta a trava: quem fechou no meio da caixa continua com ela
  por dez minutos, e ao abrir de novo a retoma.

## Consequências

- O aviso diz quem, onde e desde quando, sem depender da TI.
- O abandono compara relógios de máquinas diferentes; depende da sincronização de
  relógio do domínio.
- A caixa assumida continua com as decisões da primeira máquina no banco dela: a trava
  evita o trabalho em paralelo, não junta os bancos. O servidor interno troca o
  adaptador por um que use o banco central, sem mudar o caso de uso.
