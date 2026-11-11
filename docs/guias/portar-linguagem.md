# Portar o motor para outra linguagem

Portar é trabalho mecânico: reimplementar a especificação e provar equivalência com a
mesma [suíte de conformidade](../testes/conformidade.md).

1. **Tipos**: gere os modelos a partir de `contracts/schemas` (quicktype,
   openapi-generator, NJsonSchema). Não escreva tipos à mão.
2. **Núcleo**: reimplemente `docs/especificacoes/` na ordem: `batch-layout.md`, máscara de tinta
   (`detectors/blank_page.md`), cada detector, `sequencing.md`, `scoring.md`,
   `metadata.md`. As convenções de unidade e arredondamento estão em [`docs/especificacoes/index.md`](../especificacoes/index.md).
3. **Adaptadores**: escolha equivalentes na tabela abaixo (OpenCvSharp, PDFium,
   ZXing etc.).
4. **Executor de conformidade**: implemente o procedimento de [`docs/testes/conformidade.md`](../testes/conformidade.md).
   A implementação nova só substitui a de referência com 100% de conformidade.
5. **Troca gradual**: porte um detector por vez e rode as duas versões em paralelo,
   comparando `report.json` campo a campo.

## Adaptadores equivalentes por linguagem

Exemplos a validar no momento da migração:

| Porta | Python (referência) | C# / .NET | Java | Rust | Navegador (WebAssembly) |
| --- | --- | --- | --- | --- | --- |
| Visão computacional | OpenCV | OpenCvSharp | OpenCV Java | opencv-rust | OpenCV.js |
| Renderizar PDF | pypdfium2 | PDFium | Apache PDFBox | pdfium-render | pdf.js |
| Armazenamento | SQLite | SQLite | SQLite | SQLite | IndexedDB ou sql.js |

## O que garante a portabilidade

1. **Especificação antes do código.** Cada regra tem um documento com objetivo, entrada,
   algoritmo em pseudocódigo, parâmetros, saída e falhas conhecidas. O código Python é a
   implementação de referência, não a especificação.
2. **Tipos gerados do contrato.** Ninguém reescreve tipo à mão.
3. **Suíte de conformidade independente de linguagem**, com tolerâncias escritas.
4. **Determinismo.** Nada aleatório, ordem de processamento definida e regras de
   arredondamento na especificação.
5. **Fronteiras finas com o mundo.** O núcleo não faz entrada e saída.
