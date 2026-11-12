# Ficha: reconhecedores do número escrito

Dois reconhecedores ficam atrás da mesma porta; o padrão é escolhido pelo bench de
numeração (acerto entre as três leituras dentro do orçamento de tempo).

## trocr-small-handwritten

| Campo | Valor |
| --- | --- |
| Modelo | trocr-small-handwritten (ONNX, quantizado) |
| Origem | <https://huggingface.co/Xenova/trocr-small-handwritten> (exportação ONNX de `microsoft/trocr-small-handwritten`) |
| Versão (commit) | `02bea33ca09a70e2e2d91140a7e6e1a729606a5b` |
| Licença | MIT |

| Arquivo | Bytes | SHA-256 |
| --- | --- | --- |
| `trocr-small-handwritten/encoder_model_quantized.onnx` | 23.082.942 | `2f29edbd925f8a49c9c7d1349895f960cf09d2efdc76fe23f957048d476e0d03` |
| `trocr-small-handwritten/decoder_model_quantized.onnx` | 40.159.904 | `40166e4f975b3cecd24bb422db80eb06912777c8e8a56ab44f6bd771ec5df553` |
| `trocr-small-handwritten/tokenizer.json` | 4.494.727 | `68bcb5468c854362a615f3d2ff6a5e4091a85f4c8198993ed9a30afe0b143737` |
| `trocr-small-handwritten/config.json` | 4.515 | `ab388d889bdead2a554fc77ae4899caabdb279318e660b457afd29394e8ee43d` |
| `trocr-small-handwritten/generation_config.json` | 185 | `cce308da91e0d656e07404c70d4b9c9f5839d426f679eff6fda6dcc0e727e3b6` |
| `trocr-small-handwritten/preprocessor_config.json` | 465 | `70da3434c33eedb3b56caf4067851741dfeed02f67576dcc3c6407c2533bfaf0` |

Codificador de imagem e decodificador de texto quantizados (INT8). A tokenização usa a
biblioteca `tokenizers`, sem PyTorch.

## PP-OCRv5_mobile_rec

| Campo | Valor |
| --- | --- |
| Modelo | PP-OCRv5_mobile_rec (PaddleOCR, versão mobile) |
| Origem | <https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx> |
| Versão (commit) | `ed152b8b495f84de93cda5709d768548a9127622` |
| Licença | Apache-2.0 |

| Arquivo | Bytes | SHA-256 |
| --- | --- | --- |
| `PP-OCRv5_mobile_rec_onnx/inference.onnx` | 16.534.782 | `da72dc72ca4dc220df0dfde68c1dedc31c58d3e76a25871122e5056227d50092` |
| `PP-OCRv5_mobile_rec_onnx/inference.yml` | 148.345 | `5dfeb2777f6d0db8177d8128a8acfcf6e6276dc4ac73ea3bf0dc06d6a5e85d8e` |

O dicionário de caracteres está no `inference.yml`.

## Métricas medidas

Bench em 300 recortes sintéticos (`tools/bench_numbering.py`, sete fontes manuscritas,
20% riscados), CPU, uma thread:

| Reconhecedor | Exato | Entre as três | Ambíguo | Exato riscado | Exato limpo | ms por recorte |
| --- | --- | --- | --- | --- | --- | --- |
| PP-OCRv5_mobile_rec (padrão) | 77,7% | 85,7% | 15,7% | 42,5% | 89,0% | 5,7 |
| trocr-small-handwritten | 59,0% | 77,7% | 41,3% | 39,7% | 65,2% | 294,6 |

O PP-OCRv5 lê com busca restrita ao vocabulário de número de folha (ADR-0015).

## Limitações conhecidas

Nenhum dos dois foi ajustado com a letra dos documentos da operação. Leitura com
confiança baixa vira "ambígua" e vai para o garantidor; o resolvedor de sequência nunca
aceita uma leitura isolada.
