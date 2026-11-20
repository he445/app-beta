# 0031: "Aprovar tudo como defeito de origem" é uma operação em lote do motor

Status: aceito · Data: 2026-11-20 · Decisores: Everton Ferreira

## Contexto

O painel ganhou "Aprovar tudo (defeito de origem)": aceitar a caixa como está, com uma
ressalva. A primeira versão mandava uma decisão individual por sinalização, porque a
decisão em lote do motor ("Decidir semelhantes", ADR-0024) exigia uma regra e recusava
página faltando. Decisões individuais entram na coleta do beta como se o revisor tivesse
julgado cada sinalização, e no teste manual da caixa de 1.000 páginas 220 decisões
tomadas num clique teriam contado assim, distorcendo a medida de precisão de cada regra.
Elas também não se desfaziam de uma vez.

## Opções consideradas

1. Manter as decisões individuais e marcar na interface que vieram do "Aprovar tudo".
2. Chamar o "Decidir semelhantes" uma vez por regra, em sequência, a partir da interface.
3. Deixar a decisão em lote do motor valer para todas as regras quando o pedido não traz
   `rule`, com ressalva (`note`) e com página faltando só por pedido explícito
   (`include_missing`).

## Decisão

Opção 3. O pedido de operação em lote aceita `action` sem `rule` (todas as regras), `note`
gravada em cada decisão e `include_missing`. Página faltando continua fora por padrão; a
interface só manda `include_missing` depois que o revisor confirma, num alerta próprio, a
lista de pastas e folhas. A operação guarda `note` e `include_missing`. A opção 1 não
tiraria as decisões da coleta do beta; a 2 criaria várias operações para desfazer e
perderia a página faltando.

## Consequências

- As decisões do "Aprovar tudo" levam `operation_id`, ficam fora da coleta do beta como
  as do "Decidir semelhantes" e se desfazem de uma vez pelo Desfazer em lote.
- O contrato só relaxa: `rule` deixa de ser obrigatória com `action`, e `note` e
  `include_missing` exigem `action`. Pedidos antigos continuam válidos.
- `rule = missing_page` sem `include_missing` continua recusado com 422.
- Migração `0014_bulk_note.sql` acrescenta as duas colunas à tabela de operações.
- Testes em `tests/test_bulk_corrections.py` cobram a ressalva, a página faltando só com
  confirmação, o Desfazer em lote e as recusas.
