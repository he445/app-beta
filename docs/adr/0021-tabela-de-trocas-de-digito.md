# 0021: Tabela de trocas de dígito na leitura da numeração

Status: aceito · Data: 2026-11-18 · Decisores: Everton Ferreira

## Contexto

No relatório de testes de 18/11/2026 (ARDIS, 1.517 datas manuscritas), o reconhecedor
errou 20 leituras com confiança de 0,85 ou mais, quase todas trocas sistemáticas de um
dígito: o 2 com laço lido como 9, o 9 com rabo longo lido como 0, o dígito final trocado.
A etapa 4 da [numeração por imagem](../especificacoes/numeracao-por-imagem.md) só criava a
alternativa 1↔7, e o filtro de confiança 0,3 descartava a segunda leitura do próprio
reconhecedor. Em nenhum dos 20 casos o valor certo chegava ao resolvedor de sequência.

## Opções consideradas

1. Tabela fixa no código, com mais pares.
2. Tabela de pares com peso no perfil (`numbering.confusions`), com a padrão no código.
3. Trocar até dois dígitos por leitura.
4. Ajustar os pares e os pesos à frequência de erro do ARDIS.

## Decisão

Opção 2. A tabela vai no perfil porque a letra de cada acervo erra de um jeito, e o beta
vai medir quais trocas aparecem na letra da operação. A padrão traz os pares do relatório
(1↔7, 2↔9, 0↔9, 3↔5, 7↔9 e 0↔6), todos com peso 0,5, a regra que já valia para 1↔7. As
alternativas saem só da leitura mais confiável, um dígito por vez, e completam as leituras
do reconhecedor até cinco. A confiança mínima de 0,3 passa a valer só para a melhor
leitura. Duas trocas (opção 3) foram medidas e não acrescentaram nenhum acerto. A opção 4
foi descartada: as datas suecas não são números de folha, e ajustar a tabela a elas mede
o bench, não o acervo.

## Consequências

- Dos 20 erros com confiança alta no ARDIS, o valor certo passa a chegar ao resolvedor em
  16; a leitura exata não muda (88,0% no que o resolvedor recebe).
- O resolvedor recebe até cinco leituras por marca em vez de três. Alternativa escolhida
  deixa a página inferida, para o revisor: a tabela reduz o trabalho do garantidor, não
  aceita nada sozinha.
- A meta do relatório (97% entre as três leituras) não foi alcançada: com três vagas,
  cada alternativa toma o lugar de uma leitura do reconhecedor.
- O contrato do perfil ganha `numbering.confusions` (opcional). `tools/bench_numbering.py
  --reader` mede o que o resolvedor recebe, com a tabela do perfil.
