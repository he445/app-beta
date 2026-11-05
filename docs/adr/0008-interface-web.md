# 0008: Interface web estática com rotas por hash e token só na sessão

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

A interface precisa ser um site estático (ADR-0001), falar com o motor só pelo contrato
(ADR-0002) e permitir uma decisão por segundo pelo teclado (seção 12). A API exige
`Authorization: Bearer`, que `<img>`, `EventSource` e o OpenSeadragon não enviam.

## Decisão

- React + TypeScript + Vite, TanStack Query e OpenSeadragon (seção 14). Tipos gerados de
  `contracts/openapi.yaml` com openapi-typescript; a CI falha se estiverem desatualizados.
- Rotas por hash (`#/batches/<id>/review`): o site funciona em qualquer hospedagem estática,
  sem regra de reescrita, e sem dependência de roteador.
- Imagens são baixadas com `fetch` (com o token) e entregues como URL de objeto;
  o progresso usa SSE lido por `fetch`, com polling de reserva.
- O token fica em `sessionStorage` (some ao fechar a aba); nome do revisor e endereço do
  motor ficam em `localStorage`. Falha de armazenamento nunca impede o uso.
- A decisão na fila só de pendentes remove o item, e o mesmo índice já aponta para o
  próximo; a imagem seguinte é pré-carregada.
- Duas rotas novas no contrato (versão 0.2.0, sem quebra): `DELETE
  /findings/{id}/decision` (Ctrl+Z) e `PUT /documents/{id}/metadata/{name}` (tela 7).

## Consequências

- O login da PoC é um token compartilhado; login individual (OIDC) entra no piloto.
- Sem tiles: a página vem inteira (1–3 MB a 300 dpi). Para lotes de 10 mil páginas, a
  rota de tiles fica para a versão seguinte do contrato.
