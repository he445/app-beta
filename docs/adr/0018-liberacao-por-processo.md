# 0018: Liberação por processo, com passada final que mantém as decisões

Status: aceito · Data: 2026-11-12 · Decisores: Everton Ferreira

## Contexto

Esperar a análise da caixa inteira para começar a conferir desperdiça o tempo do
conferente. Mas algumas regras comparam com o lote (nitidez e exposição usam a mediana;
duplicata compara páginas entre processos) e a sequência só fecha com todas as páginas
do processo.

## Opções consideradas

1. Liberar por página: não serve, a numeração e a sequência precisam do processo inteiro.
2. Liberar por processo com a mediana parcial e uma passada final que reavalia tudo.
3. Analisar a caixa duas vezes (rápida e completa): dobra o custo por página.

## Decisão

Opção 2 ([especificação](../especificacoes/liberacao-por-processo.md)).

- Os processos entram na análise na ordem das pastas; cada um fica pronto quando sua
  última página é analisada, e o relatório parcial dos processos prontos é gravado.
- Regras que comparam com o lote usam a mediana do que já foi analisado e, com menos
  páginas que `min_batch_size`, os limites absolutos que já têm. A duplicata entre
  páginas fica para a passada final.
- A passada final reavalia o lote completo e é mesclada com o que está gravado:
  decisões são mantidas (inclusive de achados que a mediana completa não repetiria),
  numeração digitada e ordem manual são reaplicadas, e achado novo num processo que já
  tinha decisões marca o processo como "reavaliar".
- Corrigir tudo, salvar o lote corrigido e o relatório por caixa esperam a passada final.

## Consequências

- O conferente começa no primeiro processo pronto; a interface mostra a fila (pronto,
  analisando, na fila) e o evento `document_ready` no fluxo de progresso.
- Montar o relatório parcial a cada processo custa só avaliação (sem reabrir imagem);
  a duplicata, que é O(n²), roda uma vez na passada final.
- Ler, mesclar e gravar o relatório acontece com o banco seguro, para não perder uma
  decisão tomada no meio.
