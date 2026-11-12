# 0015: Numeração lida da imagem com detector, riscado e reconhecedor restrito

Status: aceito · Data: 2026-11-12 · Decisores: Everton Ferreira

## Contexto

No beta, a numeração de folha está escrita à mão no canto da página; não há
`numbering.json`. Sem ela, todo documento cai em "completude não verificável" e o
revisor confere a sequência inteira à mão.

## Opções consideradas

1. Só o TrOCR (manuscrito) sobre a região inteira do canto.
2. Detector de escritos + reconhecedor por caixa, com riscado por geometria e dois
   reconhecedores atrás da mesma porta (TrOCR e PP-OCRv5_mobile_rec), escolhidos por
   bench.
3. Treinar um modelo próprio com a letra da operação: sem dados antes do beta.

## Decisão

Opção 2 ([especificação](../especificacoes/numeracao-por-imagem.md)). O padrão é o
PP-OCRv5_mobile_rec, com busca restrita ao vocabulário de número de folha; o TrOCR fica
como alternativa por perfil.

Bench em 300 recortes sintéticos (sete fontes manuscritas, 20% riscados):

| Reconhecedor | Exato | Entre as três | Ambíguo | ms por recorte |
| --- | --- | --- | --- | --- |
| PP-OCRv5_mobile_rec | 77,7% | 85,7% | 15,7% | 5,7 |
| trocr-small-handwritten | 59,0% | 77,7% | 41,3% | 294,6 |

Riscado nos mesmos recortes: 72 de 73 riscados achados e nenhum falso entre os 227
limpos (nota 0,6). Nas 36 páginas dos oito cenários, 34 com as marcas certas, de 80 a
120 ms por página com detector, riscado e reconhecedor.

## Consequências

- O resolvedor não muda; o leitor só produz marcas no formato que ele já recebe.
- `numbering.json` continua tendo prioridade: conformidade e demonstração não mudam.
- Número sozinho riscado com traço fraco passa como não riscado (exigência de 0,99): a
  sequência do documento acusa a divergência e manda para o revisor.
- Os recortes confirmados pelos garantidores no beta viram a base para medir de novo e,
  se for o caso, trocar o padrão: a coleta guarda cada confirmação só nesta máquina
  (porta `FeedbackStore`), `qa feedback export` gera o pacote para o ajuste fino dentro
  da empresa e `qa beta report` calcula as métricas do piloto do banco local
  ([coleta do beta](../especificacoes/coleta-do-beta.md)).
