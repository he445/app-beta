# 0029: Lacuna implausível na numeração é leitura duvidosa, não folha faltando

Status: aceito · Data: 2026-11-20 · Decisores: Everton Ferreira

## Contexto

O detector `sequence` só transforma uma lacuna em "página faltando" quando os dois lados
foram lidos com confiança. Na caixa de regressão de 1.000 páginas isso não bastou: o leitor
de canto leu com confiança números impressos (datas, protocolos, códigos de formulário),
e o motor produziu um "Faltam fls." com mais folhas que o próprio documento e três
reordenações automáticas em processos que estavam na ordem certa. Nesses documentos não
havia numeração de folha: os valores lidos (100, 980, 3509, 0, 1733…) não formam sequência
alguma, e o resolvedor ordenava por eles.

O resolvedor (`domain/sequencing.py`) está correto para a entrada que recebe; o que falta é
um teste de plausibilidade da entrada e da saída.

## Opções consideradas

1. Mudar o resolvedor para penalizar saltos grandes. Mexe na semântica de todos os casos de
   conformidade e na relação calibrada entre os pesos.
2. Testar a plausibilidade depois de resolver, no detector, e resolver de novo com outra
   entrada quando há uma leitura isolada fora da curva.

## Decisão

Opção 2 ([especificação](../especificacoes/sequencing.md), seção 6), sem mudança em
`domain/sequencing.py`:

- Lacuna implausível: mais faltantes que `max_gap_sheets` (perfil, padrão 50) ou que o
  número de páginas do documento, a partir de `min_implausible_gap` (perfil, padrão 10).
  Vira `numbering_review` na página do salto ("Salto de fls. 20 para 1021: leitura de
  numeração duvidosa"), nunca `missing_page`.
- Leitura fora da curva: página junto a uma lacuna implausível cujas vizinhas são coerentes
  entre si e cujo valor não fica entre elas (20, 2019, 22). As marcas dela são descartadas,
  o documento é resolvido de novo e a página aparece como `ambiguous` para digitação.
- Ordem com salto implausível não é proposta: o documento fica na ordem do arquivo e recebe
  um `numbering_review` de documento. Reordenar é correção automática, e uma numeração com
  saltos implausíveis não é evidência suficiente para ela.

O piso `min_implausible_gap` existe porque documento curto com algumas folhas faltando é
caso real (o caso `lacuna-grande-no-fim`: 2 páginas, faltam 3); sem ele, toda lacuna maior
que um documento de poucas páginas iria para revisão em vez de pedir a folha.

## Consequências

- Caixa de regressão: some o "Faltam fls." maior que o documento e somem os 3 "fora de
  ordem" falsos; as folhas perdidas declaradas no `manifest.csv` continuam achadas.
- Número impresso que cria lacuna pequena continua passando (falha conhecida na
  especificação). A defesa é a de sempre: dois lados confiáveis e aprovação manual da folha
  faltante.
- Documento sem numeração de folha, mas com números impressos no canto, gera mais
  `numbering_review`. É o comportamento certo: na dúvida, revisão.
- Cobrança: casos `data-impressa-no-meio` e `salto-implausivel-sem-vizinhas-coerentes` em
  `conformance/fixtures/sequencing/cases.json`, e testes em `test_sequencing.py`.
