# 0024: Corrigir pasta, Corrigir tudo e Decidir semelhantes, inclusive durante a análise

Status: aceito · Data: 2026-11-18 · Decisores: Everton Ferreira · Revê parte da
[ADR-0018](0018-liberacao-por-processo.md)

## Contexto

No uso real do beta, três atritos apareceram na revisão:

1. "Corrigir tudo" respondia 409 durante toda a análise da caixa (ADR-0018), mas o
   conferente já está conferindo os processos prontos e quer limpar o automático da pasta
   que tem na tela.
2. Na revisão só havia "Corrigir o lote inteiro". Na Sequência, o botão por documento se
   chamava "Corrigir tudo" e corrigia só aquela pasta. Os nomes confundiam.
3. Um mesmo achado em centenas de páginas exigia uma tecla por página. Exemplo: uma caixa
   inteira sem DPI gravado gera "Resolução abaixo do exigido" em todas.

## Opções consideradas

1. Manter o 409 e só renomear os botões. Não resolve 1 nem 3.
2. Liberar a correção em lote para os processos prontos e acrescentar à mesma operação um
   filtro por regra e uma decisão a aplicar ("Decidir semelhantes").
3. Uma rota nova de decisões em lote, separada da correção em lote. Duplica progresso,
   auditoria e desfazer.

## Decisão

Opção 2 ([especificação](../especificacoes/corrections.md)).

- **Corrigir pasta** (escopo `document`) e **Corrigir tudo** (escopo `batch`) são a
  mesma operação de sempre. Com a caixa em análise, valem para os processos já prontos:
  a pasta pedida tem de estar pronta (senão 409), e "Corrigir tudo" é marcado
  `partial`. As decisões entram como as individuais, que a ADR-0018 já permitia durante
  a análise, e a passada final as mantém.
- **Decidir semelhantes**: o pedido traz `rule` e `action` (`approve`, `reject` ou
  `source_defect`). A operação aplica a mesma decisão em todas as sinalizações
  **pendentes** daquela regra no escopo, com o identificador da operação. O progresso
  e o desfazer em lote são os do "Corrigir tudo".
- `correct` não é decisão em lote: corrigir em massa continua restrito ao que é
  automático e seguro. Página faltando fica fora, porque cada uma pede decisão própria e
  salvar o lote corrigido depende disso.
- Decisão em lote não vira exemplo da coleta do beta: ninguém olhou cada página.

## Consequências

- O conferente limpa o automático e as categorias inteiras da pasta que está conferindo,
  sem esperar a caixa.
- Uma correção automática decidida com a mediana parcial (exposição, por exemplo)
  continua decidida mesmo se a mediana final não a repetir. É o mesmo comportamento da
  decisão individual na liberação por processo.
- "Aprovar todas" sem olhar é uma escolha do conferente. A interface pede confirmação e
  diz quantas serão decididas, e a auditoria guarda a operação e quem a pediu.
- Migração 0013 (`operations.rule`, `action`, `partial`); contrato 0.19.0.
