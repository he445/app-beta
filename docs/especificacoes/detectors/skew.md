# skew: Inclinação

Versão: 1.0.0 · Severidade padrão: médio (alto acima do limite de reprovação)

## Objetivo

Medir o ângulo das linhas de texto e propor endireitamento automático na cópia.

## Entrada

Máscara de tinta da área útil, no raster de análise.

## Algoritmo

Perfil de projeção: o ângulo certo é o que deixa as linhas de texto mais "nítidas" na
soma por linha.

```text
se cobertura < min_ink_coverage: inelegível
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
sinaliza se |inclinação| > flag_threshold
severidade ← alto se |inclinação| > reject_threshold, senão médio
```

## Parâmetros

| Nome | Tipo | Padrão | Faixa |
| --- | --- | --- | --- |
| `flag_threshold` | número (graus) | 0,5 | ≥ 0 |
| `reject_threshold` | número (graus) | 3,0 | ≥ 0 |
| `max_angle` | número (graus) | 10 | 1 a 45 |
| `min_ink_coverage` | número | 0,005 | 0 a 1 |

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

## Histórico de versões

- 1.0.0: versão inicial.
