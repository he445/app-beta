# Trava por caixa

Dois conferentes não podem conferir a mesma caixa em máquinas diferentes. A pasta
original é só leitura, então a trava fica na pasta compartilhada de relatórios.

## Arquivo

`<reports_dir>/travas/<caixa>.lock`, em JSON: caixa, conferente (usuário do Windows),
máquina, lote, identificador da abertura do programa, quando travou (`acquired_at`) e a
última renovação (`renewed_at`). Sem `reports_dir`, o arquivo fica em
`<data_dir>/travas/` e vale só dentro da máquina; a tela avisa.

A caixa é a primeira pasta do lote ([relatório por caixa](relatorio-por-caixa.md));
lote sem pastas de caixa é uma caixa com o nome do lote. Antes da análise, as caixas
saem dos arquivos da pasta.

## Regras

- **Abrir** (`POST /local-batches`): trava todas as caixas do lote, tudo ou nada. A
  trava é criada de forma exclusiva (dois que abrem ao mesmo tempo: só um consegue).
- Caixa travada por outra abertura: 409 com "Caixa 0412 em conferência por fulano, na
  máquina X, desde 14h00".
- **Renovar**: a interface chama `POST /batches/{id}/lock` a cada minuto enquanto o
  lote está aberto. Se outra máquina assumiu, a renovação responde 409 e a tela avisa.
- **Trava abandonada**: sem renovação há mais de 10 minutos (o programa fechou ou
  caiu). Pode ser assumida com `take_over`; o arquivo guarda de quem foi assumida
  (`taken_over_from`) e o banco registra o evento (`box_lock_events`: travar, assumir,
  soltar). Trava viva nunca é assumida.
- **Soltar**: `DELETE /batches/{id}/lock` e, ao fechar o programa, todas as travas desta
  abertura.
