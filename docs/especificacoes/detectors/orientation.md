# orientation: Página de lado ou de cabeça para baixo

Versão: 1.1.0 · Severidade padrão: médio

## Objetivo

Encontrar a página digitalizada de lado ou de cabeça para baixo e propor a rotação que a
endireita. Com confiança alta, a rotação entra no "Corrigir tudo"; com confiança média,
fica sugerida para o revisor conferir.

## Entrada

Raster de análise (cinza, 150 dpi) e a orientação prevista pela porta
`OrientationClassifier` ([ficha do modelo](../../modelos/orientacao.md)): o ângulo `a` em
{0, 90, 180, 270}, que é o giro **horário** que a página sofreu, e a probabilidade `p` de
cada ângulo. Sem modelos configurados, a regra não classifica nenhuma página.

## Algoritmo

```text
se skip_blank e cobertura_de_tinta < blank_ink_coverage: inelegível (página branca)
pouca_tinta ← skip_blank e cobertura_de_tinta < min_ink_coverage
a, p ← classificador(página)
limite ← auto_threshold se pouca_tinta, senão review_threshold
se a = 0 ou p < limite: nada
correção = girar (360 − a) mod 360 graus no sentido horário, na cópia
se p ≥ auto_threshold e não pouca_tinta: correção automática (entra no "Corrigir tudo")
senão: correção sugerida com review = verdadeiro (fica para o revisor, que aplica com C)
```

Página com pouca tinta (bilhete, despacho curto, só assinatura) é classificada, mas a
rotação só é proposta com probabilidade de pelo menos `auto_threshold` e nunca entra no
"Corrigir tudo": pouco escrito engana o modelo, e passar girada sem aviso é pior que uma
revisão a mais.

Na análise da página, quando `a ≠ 0` e `p ≥ limite`, as regras que dependem do
sentido do texto (`skew`) são medidas numa **vista girada em memória** (a página
endireitada); as demais medem a imagem original. O arquivo original nunca é tocado. Na
cópia corrigida, a rotação é aplicada na ordem canônica recorte → girar → endireitar
([correções](../corrections.md)); como rotações em torno do centro comutam, o ângulo de
inclinação medido na vista girada vale na cópia girada.

## Parâmetros

| Nome | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `auto_threshold` | número | 0,90 | 0 a 1 | Probabilidade a partir da qual a rotação é automática |
| `review_threshold` | número | 0,60 | 0 a 1 | Probabilidade a partir da qual a rotação é sugerida para revisão |
| `skip_blank` | sim/não | sim | | Não classificar página branca e exigir confiança alta na página com pouca tinta |
| `blank_ink_coverage` | número | 0,003 | 0 a 1 | Cobertura de tinta abaixo da qual a página é branca e não é classificada |
| `min_ink_coverage` | número | 0,01 | 0 a 1 | Cobertura de tinta abaixo da qual a página tem pouca tinta |

Os limites são ponto de partida conservador e são calibrados no beta: toda rotação
automática que o revisor desfizer conta como erro, e `auto_threshold` sobe até zerar.

## Saída

- `measure` e `confidence`: probabilidade `p`; `threshold`: o limite que ela passou.
- Correção `automatic/rotate`, `params.angle_deg` = giro horário que desfaz,
  `params.detected_deg` = `a`, e `params.review = true` na faixa média e na página com
  pouca tinta; nesta, também `params.low_ink = true`.
- Mensagem: "Página de lado (girada para a direita)", "de cabeça para baixo" ou "de lado
  (girada para a esquerda)", com a confiança.

## Rotação escolhida pelo revisor

`PUT /pages/{id}/rotation` com o giro horário total (0, 90, 180 ou 270). Se a página já
tem sinalização `orientation`, ela passa a propor o giro escolhido (`params.manual =
true`, `detected_deg` mantido) e é decidida como `correct`; se não tem, nasce uma
sinalização "Rotação escolhida pelo revisor" (medida 1, confiança 1) já decidida. Giro 0
aprova a sinalização existente (não girar). A cópia corrigida é regravada: versões
gravadas só são reaproveitadas quando sinalizações, ações **e parâmetros** da cadeia são
os mesmos.

## Falhas conhecidas e casos de borda

- Página branca não é classificada. Verso só com carimbo ou rubrica cai na faixa de
  pouca tinta: o carimbo não tem sentido de leitura e o modelo erra nele com confiança
  média (0,87 na base sintética), abaixo de `auto_threshold`, então não é sinalizado.
- Página paisagem (tabela, planta) gira quando o texto está de lado, como o revisor faz
  hoje. Se a operação definir outra regra para paisagem, ela vira parâmetro do perfil.
- O modelo olha o recorte central da página reduzida: página com texto só nas bordas
  tende a confiança baixa e cai na revisão ou em nada.

## Casos de conformidade

`conformance/fixtures/core`, documento `CX001/DOC0007`: páginas giradas 90°, 180° e 270°
(sinalizadas, com o giro que desfaz), página com pouco texto (não sinalizada) e página só
com carimbo (pouca tinta, não sinalizada). A ida e volta exata (girar e corrigir
devolve o original pixel a pixel) está em `engine/tests/test_orientation.py`.

## Referências

- PaddleOCR, PP-LCNet_x1_0_doc_ori (classificação de orientação de documento).

## Histórico de versões

- 1.1.0: página com pouca tinta passa a ser classificada; só sinaliza a partir de
  `auto_threshold` e sempre para revisão (novo `blank_ink_coverage` para a página branca).
  No relatório de testes de 18/11/2026, duas páginas manuscritas giradas com menos de 1%
  de tinta passavam sem sinalização.
- 1.0.0: versão inicial.
