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
180° com 0,87; por isso a página com pouca tinta só é sinalizada a partir de 0,90 e
sempre para revisão.

Dados públicos (RVL-CDIP, subset `vaclavpechtor/rvl_cdip-small-200`: 160 páginas
manuscritas e 40 formulários a cerca de 100 dpi, mais as mesmas 200 giradas ao acaso com
seed 42; 398 páginas avaliadas), perfil `sos-piloto`, medido com
`tools/bench_orientation.py` na versão 1.0.0:

| Desfecho | Páginas |
| --- | --- |
| Página certa, não sinalizada | 242 |
| Girada, corrigida automaticamente (todas certas) | 93 |
| Girada, corrigida com sugestão para revisão | 44 |
| Girada, não sinalizada (erro silencioso) | 13 |
| Girada, ângulo errado, enviada para revisão | 3 |
| Página certa, girada por engano, enviada para revisão | 3 |

Entre 0,85 e 0,90 de probabilidade aparece 1 erro em 28 correções; entre 0,80 e 0,90,
3 em 41: o `auto_threshold` de 0,90 se mantém.

No beta, as rotações confirmadas e desfeitas pelos garantidores medem o acerto na letra
e no papel reais.

Observação: o modelo raramente passa de 0,93 de probabilidade, então `auto_threshold`
acima disso desligaria a rotação automática.

## Limitações conhecidas

- Página com pouco texto ou só com carimbo: confiança baixa; a regra manda para revisão.
- Página em branco: não é classificada (pulada).
- Página com pouca tinta: classificada; só sinalizada com 0,90 ou mais, para revisão.
