# 0009: Correção em lote, aprovação manual de página faltando e lote corrigido

Status: aceito · Data: 2026-11-08 · Decisores: Everton Ferreira

## Contexto

O motor detectava defeitos, mas o resultado das correções não saía dele: cada correção
de imagem era aplicada uma página por vez numa cópia que nunca era exportada, e aceitar
a reordenação ou a remoção de página em branco só registrava a decisão. O revisor
precisa corrigir o automático com um clique, ver como o lote fica e baixar o lote
corrigido, sem que a ferramenta esconda defeitos que exigem redigitalizar.

## Opções consideradas

1. Aplicar cada correção sobre a última cópia gravada (encadeamento pela ordem das decisões).
2. Recalcular sempre a versão da página a partir do original e das decisões vigentes,
   numa ordem canônica, com as cópias como cache.
3. Gerar o lote corrigido direto do original no "Salvar", sem cópias intermediárias.

## Decisão

- **Versão de página = original + correções de imagem decididas, em ordem canônica**
  (opção 2; `spec/corrections.md`). Independe da ordem das decisões e de desfazer no
  meio da cadeia; as cópias e o log só de inserção (porta `PageVersionStore`) são cache
  e auditoria, e desfazer reaproveita a versão anterior byte a byte.
- **"Corrigir tudo"** é um caso de uso da camada application (`CorrectionService`) que
  decide `correct` só no que é automático e seguro (imagem, remoção de página em branco,
  reordenação). Página faltando exige aprovação manual; defeitos que exigem redigitalizar
  ficam pendentes e vão para a ordem de retrabalho; duplicata nunca é removida
  automaticamente (seção 9 do ADD).
- **Cada decisão em lote carrega `operation_id`** (campo opcional de `Decision`, coluna
  em `decisions`); desfazer em lote remove só as decisões que ainda o carregam.
- **Progresso real**: a operação roda em segundo plano, numa fila própria, e grava
  `done` de `total` unidades (páginas e documentos) na tabela `operations`; a interface
  consulta `GET /bulk-corrections/{id}`.
- **Salvar é recusado (409) com página faltando sem decisão.** As três decisões possíveis
  usam as ações existentes: `reject` (retrabalho), `source_defect` (defeito de origem) e
  `approve` (aprovar mesmo assim).
- **Lote corrigido** em `.zip` com TIFF Deflate (sem perda), DPI do original, ordem
  final, removidas fora, renumeração e manifesto validado contra o contrato
  (porta `CorrectedBatchWriter`).
- Contrato 0.3.0 (só adições): `POST/GET /batches/{id}/bulk-corrections`,
  `GET/DELETE /bulk-corrections/{id}`, `GET /batches/{id}/corrected-plan`,
  `POST /batches/{id}/corrected-batch`, `lote-corrigido.zip` em `GET .../exports/{name}`,
  e os esquemas `bulk-correction*`, `corrected-*` e `decision.operation_id`.

## Consequências

- O app HTTP ficou fino: a decisão individual também passou a usar o `CorrectionService`.
- Lotes antigos: linhas do log anteriores ao formato novo são ignoradas, e as versões
  são recalculadas a partir das decisões quando pedidas.
- "Salvar" gera o zip na própria requisição; para lotes de milhares de páginas a geração
  deve virar uma operação em segundo plano com progresso, como o "Corrigir tudo".
- A versão corrigida é reanalisada pelos detectores de página; regras que ainda disparam
  voltam em `result.pages[].remaining_rules`.
