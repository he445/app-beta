# 0030: Defeitos de imagem tipificados no relatório da caixa

Status: aceito · Data: 2026-11-20 · Decisores: Everton Ferreira

## Contexto

O relatório por caixa juntava como "Páginas ilegíveis" toda página confirmada (retrabalho
ou defeito de origem) numa regra de imagem: desfoque, exposição, resolução baixa e arquivo
corrompido. No teste manual da caixa de 1.000 páginas, aceitar a caixa como defeito de
origem produziu "103 páginas ilegíveis", quando a maioria se lia: eram páginas claras
demais, com resolução abaixo do exigido ou um pouco desfocadas. Para o cliente, "ilegível"
quer dizer que não dá para ler, e o relatório dizia isso de páginas legíveis.

## Opções consideradas

1. Manter "ilegível" para tudo e só trocar o texto no PDF.
2. Tirar desfoque, exposição e resolução do relatório.
3. "Ilegível" só para o arquivo que não se lê (`corrupted_file`) e os outros defeitos de
   imagem tipificados, cada um com o seu nome, em campos novos e opcionais do contrato.

## Decisão

Opção 3. `illegible` passa a contar só `corrupted_file`. Desfoque, exposição e resolução
baixa saem em `processes[].defects` (regra, rótulo, quantidade e páginas) e somam em
`totals.defects`. Uma página conta uma vez em cada tipo. Os campos novos são opcionais:
relatórios gravados antes continuam válidos e a Gestão, que lê relatórios de várias
máquinas, segue com o contrato dela (`missing` e `illegible`). A opção 2 esconderia do
cliente defeitos confirmados; a 1 deixaria a Gestão somando páginas legíveis como
ilegíveis.

## Consequências

- O PDF lista "Páginas ilegíveis", "Páginas desfocadas", "Páginas com exposição ruim
  (clara ou escura demais)" e "Páginas com resolução abaixo do exigido", com folha ou
  posição de cada uma.
- `illegible` muda de sentido: nos relatórios anteriores a este ADR ele incluía os
  defeitos de imagem. Quem somar relatórios antigos e novos precisa saber disso.
- A chave de pendências inclui os defeitos tipificados: mudar um deles gera versão nova.
- Testes em `tests/test_box_report.py` cobram a tipificação e a validade do relatório
  antigo, sem `defects`.
