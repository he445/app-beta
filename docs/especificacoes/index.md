# Especificação

Especificação independente de linguagem do motor ([princípio 6](../visao-geral/principios.md)). O código em
`engine/` é a implementação de referência; **esta pasta é a fonte do comportamento**.
Uma implementação em outra linguagem reimplementa estes documentos e prova equivalência
com a suíte de `conformance/`.

| Documento | Conteúdo |
| --- | --- |
| [`batch-layout.md`](batch-layout.md) | Como uma pasta de lote vira documentos e páginas |
| [`lote-local.md`](lote-local.md) | Lote lido no lugar: espera de estabilidade, retrato e raízes permitidas |
| [`trava-por-caixa.md`](trava-por-caixa.md) | Uma caixa conferida por uma máquina de cada vez; trava abandonada assumida com registro |
| [`liberacao-por-processo.md`](liberacao-por-processo.md) | Cada processo liberado ao ficar pronto, relatório parcial e passada final |
| [`detectors/`](detectors/blank_page.md) | Um documento por regra de página, no modelo obrigatório |
| [`sequencing.md`](sequencing.md) | Numeração, sequência e completude (regras de documento) |
| [`numeracao-por-imagem.md`](numeracao-por-imagem.md) | Leitura da numeração manuscrita no canto da página |
| [`folha-inserida.md`](folha-inserida.md) | Folha que apareceu depois: área de complementos, posição pelo número, desfazer |
| [`coleta-do-beta.md`](coleta-do-beta.md) | Exemplos rotulados do beta e definição das métricas do piloto |
| [`relatorio-por-caixa.md`](relatorio-por-caixa.md) | Pendências de cada processo da caixa, versões e onde são gravadas |
| [`gestao.md`](gestao.md) | Relatórios de todas as máquinas por conferente, período e versão do programa |
| [`scoring.md`](scoring.md) | Severidade, estado do documento, veredito e amostragem |
| [`metadata.md`](metadata.md) | Metadados do Decreto 10.278/2020 e técnicos |
| [`metadados-no-lote-corrigido.md`](metadados-no-lote-corrigido.md) | Tags e XMP no TIFF e `metadados.json` por processo, com o SHA-256 de cada arquivo |
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
