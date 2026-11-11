# Ficha: detector de escritos

| Campo | Valor |
| --- | --- |
| Modelo | PP-OCRv5_mobile_det (PaddleOCR, versão mobile) |
| Origem | <https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx> |
| Versão (commit) | `e6f4fa85f00e168c862bc462aebca69eef9b3d3d` |
| Licença | Apache-2.0 |
| Usado por | Leitura da numeração: achar cada escrito na região configurada |

| Arquivo | Bytes | SHA-256 |
| --- | --- | --- |
| `PP-OCRv5_mobile_det_onnx/inference.onnx` | 4.826.518 | `a431985659dc921974177a95adcfbb90fd9e51989a5e04d70d0b75f597b6e61d` |
| `PP-OCRv5_mobile_det_onnx/inference.yml` | 903 | `98069072e1b6b37d727fd9d9f11725faa46d6ea0de012f2ed26caea011c37699` |

## Entrada e saída

Imagem RGB normalizada (lados múltiplos de 32); saída: mapa de probabilidade de texto,
convertido em caixas pelo pós-processamento do detector (DB).

## Métricas medidas

Ainda não medidas no programa: entram com os fixtures sintéticos de numeração.

## Limitações conhecidas

Treinado também com manuscrito, mas não com a letra dos documentos da operação: o que
não for achado com segurança vai para o garantidor.
