# 0017: Documentação numa pasta só, em português, cobrada pela CI

Status: aceito · Data: 2026-11-11 · Decisores: Everton Ferreira

## Contexto

A documentação estava espalhada: especificação em `spec/`, guias em `docs/guides/`,
um `README.md` por pasta e um documento de desenho único que misturava decisão, plano e
comportamento. Quem chega para avaliar, instalar ou manter o sistema não sabia por onde
começar, e parte do texto já não descrevia o que o código faz.

## Opções consideradas

1. Manter a estrutura e só corrigir os textos.
2. Uma pasta só (`docs/`), organizada por tipo de leitor e de documento, publicada como
   site navegável e conferida na integração contínua.

## Decisão

Opção 2.

- **Uma pasta:** tudo em `docs/`. Na raiz ficam só os arquivos que o GitHub e as
  ferramentas esperam (`README.md` curto, `CHANGELOG.md`, `CONTRIBUTING.md`).
  `contracts/` continua na raiz porque é lido pelo código; a referência legível dele é
  gerada dentro de `docs/referencia/`.
- **Em português.** O código continua em inglês (ADR-0006).
- **Descreve o sistema como ele é.** O que é decisão vai para ADR; o que é comportamento
  vai para especificação ou guia. Documento de planejamento não entra no repositório.
- **Padrões:** Diátaxis para organizar (tutoriais, guias, referência, explicação), arc42
  com diagramas C4 para a arquitetura, ADRs no formato MADR, Keep a Changelog com SemVer
  e uma ficha por modelo embarcado.
- **Referência gerada:** `tools/docs/gen_reference.py` gera as páginas de API, perfis e
  linha de comando a partir do contrato e do código. Ninguém as edita à mão.
- **Site:** MkDocs Material, com busca, que também funciona offline.

## Consequências

- A especificação passa de `spec/` para `docs/especificacoes/`; os manifestos das regras
  e o esquema `detector-manifest.schema.json` apontam para o caminho novo.
- A CI roda `mkdocs build --strict`, lint de Markdown e `tools/docs/check_docs.py`, que
  reprova link relativo quebrado, referência gerada desatualizada e menção a documento de
  planejamento que não está no repositório.
- Tarefa que muda comportamento só está pronta com a página correspondente atualizada.
