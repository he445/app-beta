# Glossário

Domínio em português, código em inglês (ADR-0006).

| Português | Código | Definição |
| --- | --- | --- |
| Lote | `Batch` | Conjunto de documentos digitalizados enviado para conferência |
| Documento | `Document` | Arquivo multipágina ou pasta de imagens de página única |
| Página | `Page` | Uma imagem: uma página de arquivo, frente ou verso de uma folha |
| Folha (fls.) | `Folio` | Número de folha escrito no papel: `12`, `12-A`, `12v` |
| Marca de numeração | `Mark` | Número encontrado na região de numeração, com até 3 leituras |
| Sinalização | `Finding` | Defeito detectado, com medida, limiar, confiança e correção |
| Regra | `rule` | Identificador de um tipo de sinalização (`blur`, `missing_page`...) |
| Detector | `PageDetector` | Função pura que mede e avalia uma regra de página |
| Linha de base | `Baseline` | Mediana e desvio robusto de uma medida no lote |
| Correção proposta | `Correction` | Automática, ação física ou escalada para decisão humana |
| Decisão do revisor | `Decision` | Aprovar (A), corrigir (C), reprovar (R), defeito de origem (O) |
| Perfil do cliente | `Profile` | Limiares, regras de numeração, estações e padrão de nomes |
| Severidade | `Severity` | Crítico, alto, médio, baixo |
| Estado do documento | `DocumentState` | Verde, amarelo, vermelho |
| Veredito | `Verdict` | Aprovado, aprovado com ressalvas, reprovado |
| Defeito de origem | `SourceDefect` (`source_defect`) | O papel já veio assim; não reprova o documento |
| Ordem de retrabalho | `ReworkOrder` (`rework_order.csv`) | Ações físicas por estação, caixa, documento e folha |
| Amostragem dos verdes | `green_sample` | Documentos sem sinalização sorteados para revisão humana |
| Estação | `Station` | Scanner ou posto de captura, ligado a um local no perfil |
| Gabarito | `gabarito.json` | Lista dos defeitos inseridos na base sintética |
| Fila de revisão | `buildQueue` (ui) | Sinalizações ordenadas por severidade para decisão pelo teclado |
