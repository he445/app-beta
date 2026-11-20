# orientation: Página de lado ou de cabeça para baixo

Versão: 1.4.0 · Severidade padrão: médio

## Objetivo

Encontrar a página digitalizada de lado ou de cabeça para baixo e propor a rotação que a
endireita. Com confiança alta, a rotação entra no "Corrigir tudo"; com confiança média,
fica sugerida para o revisor conferir.

## Entrada

Raster de análise (cinza, 150 dpi) e a orientação prevista pela porta
`OrientationClassifier` ([ficha do modelo](../../modelos/orientacao.md)): o ângulo `a` em
{0, 90, 180, 270}, que é o giro **horário** que a página sofreu, e a probabilidade `p` de
cada ângulo. Sem modelos configurados, a regra não classifica nenhuma página.

O classificador recebe a **vista de conteúdo**: a página sem as faixas pretas que
[`black_borders`](black_borders.md) sinalizaria, com folga de 0,5% do lado (ADR-0027). O
modelo olha um recorte central, e a faixa preta dentro dele fazia uma página girada passar
como de pé. Só a faixa acima de `min_fraction` é cortada: uma ou duas linhas escuras da
borda do scanner mudam o recorte central sem tirar nada que atrapalhe.

**Inclinação antes de classificar.** Antes do classificador, a inclinação é estimada na
vista de conteúdo (o mesmo cálculo de [`skew`](skew.md)). Se ela passar de
`deskew_before_orient` com confiança de pelo menos `deskew_min_confidence`, o classificador
também recebe uma cópia endireitada em memória, e vale a leitura de maior probabilidade
entre as duas. Numa página de lado a busca de ângulo não acha linhas e devolve confiança
baixa, então nada é endireitado por engano. Na caixa de regressão, das 41 páginas com
inclinação acima de 2°, a vista crua errou uma (5,9° lida como de cabeça para baixo com
0,898) e a endireitada sozinha criou uma orientação incerta falsa (2,8°, de 0,77 para
0,33); a leitura mais confiante acertou as 41. Quando a página fica de pé, essa inclinação
é a que a regra `skew` usa, sem medir de novo.

## Algoritmo

```text
se skip_blank e cobertura_de_tinta < blank_ink_coverage: inelegível (página branca)
pouca_tinta ← skip_blank e cobertura_de_tinta < min_ink_coverage
a, p ← classificador(página)
limite ← auto_threshold se pouca_tinta, senão review_threshold
se a = 0 ou p < limite:
    se pouca_tinta ou p₀ ≥ upright_min_probability: nada
    senão: orientação incerta (abaixo)
correção = girar (360 − a) mod 360 graus no sentido horário, na cópia
se p ≥ auto_threshold e não pouca_tinta: correção automática (entra no "Corrigir tudo")
senão: correção sugerida com review = verdadeiro (fica para o revisor, que aplica com C)
```

Página com pouca tinta (bilhete, despacho curto, só assinatura) é classificada, mas a
rotação só é proposta com probabilidade de pelo menos `auto_threshold` e nunca entra no
"Corrigir tudo": pouco escrito engana o modelo, e passar girada sem aviso é pior que uma
revisão a mais.

**Orientação incerta.** Quando nenhuma rotação passa do limite e a probabilidade de a
página estar de pé, `p₀`, fica abaixo de `upright_min_probability`, o modelo não sabe: a
página vai para revisão com a rotação mais provável entre 90°, 180° e 270° sugerida
(`params.review = true`, `params.uncertain = true`), nunca no "Corrigir tudo". O revisor
aplica com C ou deixa de pé (giro 0). Sem as probabilidades de cada ângulo, `p₀` é o maior
valor possível: `p` se `a = 0`, senão `1 − p`. Não vale para a página com pouca tinta,
porque no carimbo e na rubrica o modelo espalha a probabilidade sem haver texto. Com
`upright_min_probability` = 0, a orientação incerta fica desligada.

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
| `upright_min_probability` | número | 0,5 | 0 a 1 | Probabilidade de 0° abaixo da qual a página sem rotação convincente vai para revisão como orientação incerta |
| `skip_blank` | sim/não | sim | | Não classificar página branca e exigir confiança alta na página com pouca tinta |
| `blank_ink_coverage` | número | 0,003 | 0 a 1 | Cobertura de tinta abaixo da qual a página é branca e não é classificada |
| `min_ink_coverage` | número | 0,01 | 0 a 1 | Cobertura de tinta abaixo da qual a página tem pouca tinta |
| `deskew_before_orient` | número (graus) | 2,0 | ≥ 0 | Inclinação acima da qual o classificador também lê a cópia endireitada |
| `deskew_min_confidence` | número | 0,3 | 0 a 1 | Confiança mínima da inclinação para endireitar antes de classificar |

Os limites são ponto de partida conservador e são calibrados no beta: toda rotação
automática que o revisor desfizer conta como erro, e `auto_threshold` sobe até zerar.

## Saída

- `measure` e `confidence`: probabilidade `p`; `threshold`: o limite que ela passou. Na
  orientação incerta, `measure` = `p₀`, `threshold` = `upright_min_probability` e
  `confidence` = `1 − p₀`.
- Correção `automatic/rotate`, `params.angle_deg` = giro horário que desfaz,
  `params.detected_deg` = `a`, e `params.review = true` na faixa média e na página com
  pouca tinta; nesta, também `params.low_ink = true`. Na orientação incerta,
  `detected_deg` é a rotação mais provável e `params.uncertain = true`.
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
  tende a confiança baixa e cai na revisão (sugerida ou incerta).
- Texto muito inclinado (4° ou mais) tira a certeza de 0°: a página torta pode vir com
  orientação incerta junto com a sinalização de inclinação (coocorrência aceita na
  conformidade).

## Casos de conformidade

`conformance/fixtures/core`, documento `CX001/DOC0007`: páginas giradas 90°, 180° e 270°
(sinalizadas, com o giro que desfaz), página com pouco texto (não sinalizada) e página só
com carimbo (pouca tinta, não sinalizada). A ida e volta exata (girar e corrigir
devolve o original pixel a pixel) está em `engine/tests/test_orientation.py`.

## Referências

- PaddleOCR, PP-LCNet_x1_0_doc_ori (classificação de orientação de documento).

## Histórico de versões

- 1.4.0: com inclinação forte e confiável, classifica também a cópia endireitada e fica com
  a leitura mais confiante (`deskew_before_orient`, `deskew_min_confidence`).
- 1.3.0: classifica a vista de conteúdo, sem as faixas pretas (ADR-0027).
- 1.2.0: orientação incerta (`upright_min_probability`): sem rotação convincente e com
  0° abaixo de 0,5, a página vai para revisão em vez de passar como de pé. No kit público,
  as giradas sem sinalização caem de 11 para 3, as revisões sobem de 52 para 71 e 5,7% das
  páginas de pé vão para revisão.
- 1.1.0: página com pouca tinta passa a ser classificada; só sinaliza a partir de
  `auto_threshold` e sempre para revisão (novo `blank_ink_coverage` para a página branca).
  No relatório de testes de 18/11/2026, duas páginas manuscritas giradas com menos de 1%
  de tinta passavam sem sinalização.
- 1.0.0: versão inicial.
