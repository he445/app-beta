# Liberação por processo

O conferente não espera a caixa inteira: cada processo (documento) é liberado assim que
fica pronto, e o resto da caixa é analisado enquanto ele trabalha (ADR-0018).

## Ordem e unidade

- A unidade de liberação é o **processo**: a sequência e a numeração só fecham com todas
  as páginas dele.
- Os processos entram na análise na ordem natural das pastas
  ([layout do lote](batch-layout.md)); os processos de análise pegam as páginas do
  primeiro processo antes das do segundo.
- O processo fica pronto quando a última página dele é analisada. O último processo da
  caixa sai junto com a passada final.

## Relatório parcial

A cada processo pronto, o motor monta o relatório **dos processos prontos** e o grava
sem fechar o lote (`status` continua `processing`):

- regras de página com a mediana das páginas já analisadas; com menos páginas elegíveis
  que `min_batch_size`, os limites absolutos de cada regra;
- sequência, completude e metadados de cada processo pronto;
- **sem** duplicata entre páginas (fica para a passada final).

O status do lote traz `documents`: `ready` (prontos, na ordem) e `pending` (os que
faltam; o primeiro está em análise). O fluxo `GET /batches/{id}/events` emite
`document_ready` (`id`, `name`, `ready`, `pending`) para cada processo que fica pronto.

Enquanto a caixa é analisada, dá para decidir sinalizações, digitar numeração e
reordenar. Corrigir tudo, salvar o lote corrigido e gerar o relatório por caixa
respondem 409 até a passada final.

## Passada final e mescla

Quando a caixa termina, o motor monta o relatório do lote inteiro (com a duplicata) e o
mescla com o gravado:

1. Sinalização com o mesmo identificador herda a decisão gravada.
2. Sinalização decidida que a passada final não repetiu continua, com a decisão (era
   uma decisão de pessoa).
3. Metadados confirmados pelo revisor continuam confirmados.
4. Numeração digitada e ordem manual são reaplicadas (re-resolução da sequência).
5. Processo que tinha alguma decisão e ganhou sinalização nova recebe `reevaluate` com
   os identificadores das novas: ele volta para a fila como "reavaliar", só com elas
   para decidir.

O resumo, os estados e o veredito são recalculados depois da mescla. Ler, mesclar e
gravar acontecem com o banco seguro, sem outra requisição no meio.
