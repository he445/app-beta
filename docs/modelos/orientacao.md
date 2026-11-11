# Ficha: orientação da página

| Campo | Valor |
| --- | --- |
| Modelo | PP-LCNet_x1_0_doc_ori (PaddleOCR) |
| Origem | <https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_doc_ori_onnx> |
| Versão (commit) | `7330ab7039123e46af2dc03154b9969aa412c61d` |
| Licença | Apache-2.0 |
| Usado por | Regra de orientação da página |

| Arquivo | Bytes | SHA-256 |
| --- | --- | --- |
| `PP-LCNet_x1_0_doc_ori_onnx/inference.onnx` | 6.788.069 | `af9a0a4f317ff0709ce752067807f819cb15d883f8ecad89f28df1c6ee2d9c92` |
| `PP-LCNet_x1_0_doc_ori_onnx/inference.yml` | 766 | `9e195eb729a8173588cd0e8a852c8b373aa606e79e77b4ac7d8346f5426caf26` |

## Entrada e saída

Pré-processamento do `inference.yml` publicado com o modelo: lado menor redimensionado
para 256, recorte central de 224 × 224, RGB normalizado (média 0,485 0,456 0,406; desvio
0,229 0,224 0,225), formato CHW. Saída: probabilidade de cada uma das quatro classes,
`0`, `90`, `180` e `270`.

## Métricas medidas

Base sintética (páginas A5 a 300 dpi com texto, `tools/synth`): em 12 páginas (3 de pé e
3 em cada ângulo), 12 acertos, todos com probabilidade entre 0,92 e 0,93. Página com
pouco texto (cobertura 0,013): sem sinalização. Página só com carimbo: o modelo dizia
180° com 0,87; por isso página quase branca não é classificada.

No beta, as rotações confirmadas e desfeitas pelos garantidores medem o acerto na letra
e no papel reais.

Observação: o modelo raramente passa de 0,93 de probabilidade, então `auto_threshold`
acima disso desligaria a rotação automática.

## Limitações conhecidas

- Página com pouco texto ou só com carimbo: confiança baixa; a regra manda para revisão.
- Página em branco: não é classificada (pulada).
