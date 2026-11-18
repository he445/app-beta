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

Dados públicos (relatório de testes de 18/11/2026): ARDIS Dataset I, parte III (1.517
datas de 4 dígitos de registros paroquiais suecos, com os 22 rótulos errados da planilha
corrigidos e os 3 ambíguos fora) e CVL Digit Strings (125 sequências de até 5 dígitos;
licença só para pesquisa: medir, nunca ajustar). A coluna "leitor" mede o que o resolvedor
de sequência recebe (`tools/bench_numbering.py --reader`): a etapa 4 da
[numeração por imagem](../especificacoes/numeracao-por-imagem.md), antes e depois da
tabela de trocas configurável.

| PP-OCRv5_mobile_rec | Exato | Entre as três | Entre as cinco | ms por recorte |
| --- | --- | --- | --- | --- |
| ARDIS, leitura crua do reconhecedor | 89,1% | 95,8% | — | 8 |
| ARDIS, leitor antes (filtro 0,3 nas três leituras, só 1↔7) | 88,0% | 90,0% | — | 8 |
| ARDIS, leitor depois (tabela padrão, até cinco leituras) | 88,0% | 92,0% | 95,6% | 8,5 |
| CVL, leitura crua do reconhecedor | 67,2% | 76,8% | — | 14 |
| CVL, leitor antes | 60,0% | 61,6% | — | 14 |
| CVL, leitor depois | 60,0% | 66,4% | 69,6% | 14 |

Dos 20 erros reais com confiança de 0,85 ou mais no ARDIS (o reconhecedor com certeza do
dígito errado), o valor certo chegava ao resolvedor em nenhum antes e chega em 16 depois:
o filtro de 0,3 descartava a segunda leitura do reconhecedor, quase sempre abaixo disso.
A meta de 97% entre as três leituras não foi alcançada: com três vagas, cada alternativa
toma o lugar de uma leitura do reconhecedor, e os pares que faltariam (9→3, 1→5, 7→8, 4→7
e outros, um ou dois casos cada) só se justificariam ajustando a tabela às datas do ARDIS.

### Confiabilidade da confiança

Medida no ARDIS com o gabarito corrigido (`tools/bench_numbering.py --reliability`),
acerto da primeira leitura com formato de folha por faixa de confiança:

| Faixa | n | Acerto | Confiança média |
| --- | --- | --- | --- |
| 0,50–0,55 | 34 | 50,0% | 0,524 |
| 0,55–0,60 | 35 | 65,7% | 0,574 |
| 0,60–0,65 | 44 | 56,8% | 0,626 |
| 0,65–0,70 | 38 | 60,5% | 0,674 |
| 0,70–0,75 | 44 | 81,8% | 0,723 |
| 0,75–0,80 | 43 | 74,4% | 0,775 |
| 0,80–0,85 | 58 | 93,1% | 0,825 |
| 0,85–0,90 | 91 | 92,3% | 0,876 |
| 0,90–0,95 | 159 | 98,1% | 0,928 |
| 0,95–1,00 | 854 | 98,8% | 0,984 |

| Limiar | Leituras acima | Erro acima |
| --- | --- | --- |
| 0,85 | 72,8% | 1,81% (20) |
| 0,90 | 66,8% | 1,28% (13) |
| 0,95 | 56,3% | 1,17% (10) |
| 0,97 | 47,6% | 0,97% (7) |
| 0,98 | 38,4% | 0,69% (4; intervalo de 95% de 0,27% a 1,75%) |
| 0,99 | 25,0% | 0,53% (2) |

No ARDIS, a confiança já é razoavelmente calibrada (erro de calibração esperado de
0,035): a faixa de cima acerta o que promete, e as faixas de 0,70 a 0,95 acertam mais
do que dizem. Errar
com 1,00 é o 1,2% de erro que a faixa 0,95–1,00 anuncia, não descalibração. Por isso
nenhuma calibração foi aplicada: uma calibração monotônica (temperatura ou isotônica)
subiria as faixas de 0,70 a 0,95 e aumentaria o erro acima de 0,85. O que deixa a faixa
confiável com erro de até 1% é o limiar: o perfil `sos-piloto` usa
`numbering.image_high_confidence` = 0,98 nas marcas lidas da imagem. Em validação cruzada
de cinco partes, mirando 0,8% no treino, o limiar escolhido ficou entre 0,96 e 0,985 e o
erro medido fora da amostra foi 0,91%. No CVL (125 recortes, fora do domínio) a confiança
é pior (erro de calibração de 0,18), com 0 erros em 15 leituras acima de 0,98.

## Limitações conhecidas

Nenhum dos dois foi ajustado com a letra dos documentos da operação. O limiar de 0,98
foi medido em datas suecas do século XIX: refazer a medida com as cerca de 200 páginas
reais anotadas pelos garantidores antes de confiar nele no acervo. Leitura com
confiança baixa vira "ambígua" e vai para o garantidor; o resolvedor de sequência nunca
aceita uma leitura isolada.
