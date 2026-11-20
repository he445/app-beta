# skew: Inclinação

Versão: 1.3.0 · Severidade padrão: médio (alto acima do limite de reprovação)

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
pontuação(img, a) ← gire img a graus no sentido anti-horário em torno do centro
                     (interpolação bilinear, fundo 0);
                     s ← soma por linha; retorne Σ (s[i+1] − s[i])²
grossa ← img reduzida à metade (média de área)
a₁ ← argmax pontuação(grossa, a) para a = −max_angle … +max_angle, passo 0,5
a₂ ← argmax pontuação(img, a) para a = a₁ − 0,6 … a₁ + 0,6, passo 0,05
empate: o primeiro ângulo da varredura (do menor para o maior)
inclinação ← a₂   (girar a₂ anti-horário endireita conteúdo inclinado a₂ no sentido horário)
confiança ← limitar(2 × (p(a₂) − p(0)) / p(a₂), 0, 1)

avaliação:
se |inclinação| ≤ flag_threshold: nada
se confiança < min_flag_confidence: nada   (o ângulo achado pontua igual a 0°)
se pouca_tinta e |inclinação| ≤ low_ink_min_angle: nada   (poucas linhas: estimativa ruidosa)
sinaliza; severidade ← alto se |inclinação| > reject_threshold, senão médio
correção deskew automática se confiança ≥ min_auto_confidence e não pouca_tinta; senão
para revisão (params.review = verdadeiro, fora do "Corrigir tudo"); na pouca tinta, com a
confiança pela metade e params.low_ink = verdadeiro
```

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

- 1.3.0: mede a página com pouca tinta (de `review_min_ink_coverage` a `min_ink_coverage`),
  sempre para revisão e acima de `low_ink_min_angle`.
- 1.2.0: confiança mínima para sinalizar (`min_flag_confidence`) e para corrigir sozinho
  (`min_auto_confidence`), ADR-0028; mede a vista de conteúdo, de pé (ADR-0027).
- 1.1.0: `min_ink_coverage` sobe para 0,01, o limite de página quase branca: verso só
  com carimbo ou rubrica não é avaliado por esta regra (a página já vai ao revisor como
  quase branca).
- 1.0.0: versão inicial.
