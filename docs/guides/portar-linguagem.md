# Portar o motor para outra linguagem

Portar é trabalho mecânico: reimplementar a especificação e provar equivalência com a
mesma suíte (seção 16 do ADD).

1. **Tipos**: gere os modelos a partir de `contracts/schemas` (quicktype,
   openapi-generator, NJsonSchema). Não escreva tipos à mão.
2. **Núcleo**: reimplemente `spec/` na ordem: `batch-layout.md`, máscara de tinta
   (`detectors/blank_page.md`), cada detector, `sequencing.md`, `scoring.md`,
   `metadata.md`. As convenções de unidade e arredondamento estão em `spec/README.md`.
3. **Adaptadores**: escolha equivalentes na tabela da seção 16 do ADD (OpenCvSharp,
   PDFium, ZXing etc.).
4. **Executor de conformidade**: implemente o procedimento de `conformance/README.md`.
   A implementação nova só substitui a de referência com 100% de conformidade.
5. **Troca gradual**: porte um detector por vez e rode as duas versões em paralelo,
   comparando `report.json` campo a campo.
