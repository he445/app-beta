# Especificação

Especificação independente de linguagem do motor ([princípio 6](../visao-geral/principios.md)). O código em
`engine/` é a implementação de referência; **esta pasta é a fonte do comportamento**.
Uma implementação em outra linguagem reimplementa estes documentos e prova equivalência
com a suíte de `conformance/`.

| Documento | Conteúdo |
| --- | --- |
| [`batch-layout.md`](batch-layout.md) | Como uma pasta de lote vira documentos e páginas |
| [`detectors/`](detectors/blank_page.md) | Um documento por regra de página, no modelo obrigatório |
| [`sequencing.md`](sequencing.md) | Numeração, sequência e completude (regras de documento) |
| [`scoring.md`](scoring.md) | Severidade, estado do documento, veredito e amostragem |
| [`metadata.md`](metadata.md) | Metadados do Decreto 10.278/2020 e técnicos |
| [`corrections.md`](corrections.md) | Versão corrigida, "Corrigir tudo", desfazer em lote e lote corrigido |

## Convenções

- Unidades do contrato: pixels com origem no canto superior esquerdo, ângulos em graus
  (positivo = sentido horário), resolução em dpi, datas ISO 8601 UTC, reais em float64.
- **Raster de análise:** página em cinza 8 bits reduzida a 150 dpi por média de área
  (sem DPI gravado, o lado menor é tratado como 210 mm). Coordenadas em `region` são
  convertidas de volta para pixels do original.
- **Linha de base do lote:** para cada medida, mediana e desvio robusto
  `σ = 1,4826 × MAD` sobre as páginas elegíveis. Valores não finitos são ignorados.
- **Determinismo:** nenhuma etapa usa aleatoriedade; empates são resolvidos pela ordem
  estável descrita em cada documento.
- **Arredondamento:** `confidence` com 4 casas; demais medidas sem arredondamento, salvo
  indicação.
