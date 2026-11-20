# skew: Inclinação

Versão: 1.4.0 · Severidade padrão: médio (alto acima do limite de reprovação)

## Objetivo

Medir o ângulo das linhas de texto e propor endireitamento automático na cópia.

## Entrada

Máscara de tinta da área útil, no raster de análise.

## Algoritmo

Perfil de projeção: o ângulo certo é o que deixa as linhas de texto mais "nítidas" na
soma por linha.

```text
se cobertura < review_min_ink_coverage: inelegível
pouca_tinta ← cobertura < min_ink_coverage   (medida, mas fora da linha de base do lote)
img ← máscara em uint8 (0 ou 255)
pontuação(img, a) ← gire img a graus no sentido anti-horário em torno do centro
                     (interpolação bilinear, fundo 0);
                     s ← soma por linha (cv2.reduce, inteiro); retorne Σ (s[i+1] − s[i])²
pontuação'(img, a) ← pontuação(img, a), mas 0° vira atan(1 / largura de img)
                     (giro mínimo que interpola como os outros ângulos)
quarto, metade ← img reduzida a 1/4 e a 1/2 (média de área)
a₁ ← argmax pontuação'(quarto, a) para a = −max_angle … +max_angle, passo 1
a₂ ← argmax pontuação'(metade, a) para a = a₁ − 1 … a₁ + 1, passo 0,25
c ← pico da parábola por a₂ − 0,25, a₂, a₂ + 0,25 (limitado a ±0,25), no passo de 0,05
a₃ ← argmax pontuação(img, a) para a = c − 0,3 … c + 0,3, passo 0,05
empate: o primeiro ângulo da varredura (do menor para o maior)
se p(0) ≥ p(a₃): inclinação ← 0, confiança ← 0   (nada pontua melhor que a página como está)
inclinação ← a₃   (girar a₃ anti-horário endireita conteúdo inclinado a₃ no sentido horário)
confiança ← limitar(2 × (p(a₃) − p(0)) / p(a₃), 0, 1)

avaliação:
se |inclinação| ≤ flag_threshold: nada
se confiança < min_flag_confidence: nada   (o ângulo achado pontua igual a 0°)
se pouca_tinta e |inclinação| ≤ low_ink_min_angle: nada   (poucas linhas: estimativa ruidosa)
sinaliza; severidade ← alto se |inclinação| > reject_threshold, senão médio
correção deskew automática se confiança ≥ min_auto_confidence e não pouca_tinta; senão
para revisão (params.review = verdadeiro, fora do "Corrigir tudo"); na pouca tinta, com a
confiança pela metade e params.low_ink = verdadeiro
```

As passadas grossas existem por tempo: a busca da 1.3.0 (41 giros na metade da resolução
e 25 na cheia, em `float32`) era um terço do tempo da página. O 0° desviado corrige um
viés: girar 0° não interpola, todo outro ângulo interpola, e na resolução reduzida isso
dava a 0° um perfil mais nítido que o do ângulo certo. Na metade da resolução o pico ainda
é largo e puxado para 0°; por isso a passada final parte do pico da parábola e cobre ±0,3°.
A passada final mede como a 1.3.0. Na caixa de regressão de 1.000 páginas, 3 páginas
limpas mudaram mais que 0,05° (de −1,9°, −2,8° e −0,3° para 0°), e nenhuma sinalização
mudou: a −2,8° era de pouca tinta, abaixo de `low_ink_min_angle`, e as outras duas tinham
confiança abaixo de `min_flag_confidence` ou ângulo abaixo de `flag_threshold`.

A medida é feita na vista de conteúdo, sem as faixas pretas do digitalizador, já de pé
(ADR-0027). Quando a página não é girada, vale a inclinação estimada antes de classificar a
orientação, sem medir de novo.

## Parâmetros

| Nome | Tipo | Padrão | Faixa |
| --- | --- | --- | --- |
| `flag_threshold` | número (graus) | 0,5 | ≥ 0 |
| `reject_threshold` | número (graus) | 3,0 | ≥ 0 |
| `max_angle` | número (graus) | 10 | 1 a 45 |
| `min_ink_coverage` | número | 0,01 | 0 a 1 |
| `min_flag_confidence` | número | 0,1 | 0 a 1 |
| `min_auto_confidence` | número | 0,3 | 0 a 1 |
| `review_min_ink_coverage` | número | 0,003 | 0 a 1 |
| `low_ink_min_angle` | número (graus) | 3,0 | ≥ 0 |

## Saída

`measure` = |inclinação| em graus; `threshold` = `flag_threshold`; correção
`automatic/deskew` com `params.skew_deg` = inclinação com sinal (positivo = horário).

## Falhas conhecidas e casos de borda

- A regra de negócio "acima de 3° reprova" vira severidade **alto** (exige revisão),
  porque a correção automática continua possível. A validar com os garantidores.
- Tabela girada ou carimbo inclinado numa página reta: vale a orientação dominante.
- Páginas em paisagem e rotações de 90°/180° são do detector de orientação (fase seguinte).

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0001/0004.tif` (+2,0°) e `CX001/DOC0002/0002.tif`
(−4,0°), tolerância ±0,1° em `conformance/tolerances.yaml`.

## Referências

- Hull, *Document image skew detection: survey and annotated bibliography*, 1998.

A página com pouca tinta que já é "quase branca" (regra `blank_page`) não recebe este aviso:
a quase branca já leva o conferente a ela. `low_ink_min_angle` foi escolhido na caixa de
regressão: as inclinações inseridas em páginas com pouca tinta eram de 3,9° e 5,95°; nas
outras páginas com pouca tinta a estimativa achou de 0,65° a 2,8°, em manuscrito e em
etiquetas, sem inclinação inserida.

## Histórico de versões

- 1.4.0: busca em três passadas (um quarto, metade e resolução cheia) sobre `uint8`, com
  o 0° desviado nas passadas grossas; com 0° pontuando melhor que o ângulo achado, a
  inclinação é 0. Mesma detecção, cerca de 3 vezes mais rápida.
- 1.3.0: mede a página com pouca tinta (de `review_min_ink_coverage` a `min_ink_coverage`),
  sempre para revisão e acima de `low_ink_min_angle`.
- 1.2.0: confiança mínima para sinalizar (`min_flag_confidence`) e para corrigir sozinho
  (`min_auto_confidence`), ADR-0028; mede a vista de conteúdo, de pé (ADR-0027).
- 1.1.0: `min_ink_coverage` sobe para 0,01, o limite de página quase branca: verso só
  com carimbo ou rubrica não é avaliado por esta regra (a página já vai ao revisor como
  quase branca).
- 1.0.0: versão inicial.
