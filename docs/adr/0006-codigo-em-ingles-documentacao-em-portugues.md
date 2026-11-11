# 0006: Código em inglês, documentação em português, com glossário

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

O domínio e o público (supervisão da SOS DOCS) falam português; bibliotecas, geradores
e outras linguagens esperam identificadores em inglês.

## Decisão

Identificadores, campos do contrato e nomes de regra em inglês (`snake_case` no
contrato). Documentação, docstrings, mensagens ao revisor e commits em português.
`docs/glossario.md` liga os dois vocabulários.

## Consequências

- Termo novo de domínio exige entrada no glossário no mesmo PR.
- Mensagens das sinalizações (`message`) são em português e não fazem parte da
  conformidade entre linguagens.
