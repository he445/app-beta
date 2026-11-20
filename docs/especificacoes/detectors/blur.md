# blur: Desfoque

Versão: 1.2.0 · Severidade padrão: crítico

## Objetivo

Encontrar páginas desfocadas, em que a informação pode estar perdida e a única correção
aceitável é redigitalizar.

## Entrada

Raster de análise (cinza, 150 dpi), máscara de tinta e área útil (ver
[`blank_page.md`](blank_page.md#máscara-de-tinta-e-área-útil)).

A medida é feita na **vista de conteúdo**: a página sem as faixas pretas do digitalizador
que [`black_borders`](black_borders.md) sinalizaria (acima de `min_fraction`), com folga de
0,5% do lado (ADR-0027). Sem faixa, a vista é a própria página.

Componentes de tinta grandes (área de pelo menos `solid_min_area` da página) e sólidos
(área sobre a da envoltória convexa de pelo menos `solid_min_solidity`) saem da máscara e
da mediana que calcula o contraste: são faixa preta estreita demais para `black_borders`,
tarja ou bloco escuro, dentro dos quais o Laplaciano é zero e a mediana vai para o preto.

## Algoritmo

```text
se cobertura_de_tinta < min_ink_coverage: página inelegível (não avaliada, fora da mediana)
contraste ← brilho_do_papel − mediana(cinza nos pixels de tinta)
se contraste < 1: inelegível
L ← Laplaciano 3×3 [0 1 0; 1 −4 1; 0 1 0] da área útil, em float64
M ← máscara de tinta da área útil dilatada por um quadrado 3×3
energia ← média(L² nos pixels de M) / contraste²

avaliação:
se o lote tem ≥ min_batch_size páginas elegíveis:
    limiar ← relative_threshold × mediana(energia do lote)
senão:
    limiar ← absolute_threshold
sinaliza se energia < limiar
confiança ← limitar(0,5 + 0,5 × (1 − energia / limiar), 0, 1)
```

A divisão pelo contraste ao quadrado separa desfoque de exposição: escurecer ou desbotar
a página multiplica o Laplaciano pelo mesmo fator do contraste. Medir só junto à tinta
torna a medida independente da quantidade de texto.

## Parâmetros

| Nome | Tipo | Padrão | Faixa |
| --- | --- | --- | --- |
| `relative_threshold` | número | 0,4 | 0 a 1 |
| `absolute_threshold` | número | 0,6 | ≥ 0 |
| `min_batch_size` | inteiro | 5 | ≥ 1 |
| `min_ink_coverage` | número | 0,01 | 0 a 1 |
| `solid_min_area` | número | 0,02 | 0 a 1 |
| `solid_min_solidity` | número | 0,9 | 0 a 1 |

## Saída

`measure` = energia; `threshold` = limiar usado; correção `physical/rescan`.

## Falhas conhecidas e casos de borda

- Página quase sem texto é inelegível: desfoque nela passa despercebido.
- Um lote inteiro desfocado não se destaca da própria mediana; o limiar absoluto só vale
  para lotes pequenos. A amostragem dos verdes ([pontuação](../scoring.md)) é a defesa.
- Desfoque reduz o contraste medido, então a página costuma disparar também
  [`exposure`](exposure.md) (coocorrência aceita na conformidade).

## Casos de conformidade

`conformance/fixtures/core` (gerado): `CX001/DOC0001/0002.tif`.

## Referências

- Pech-Pacheco et al., *Diatom autofocusing in brightfield microscopy: a comparative study*, 2000
  (variância do Laplaciano).

## Histórico de versões

- 1.2.0: mede a vista de conteúdo, sem as faixas pretas; componentes sólidos e grandes saem
  da máscara e do contraste (ADR-0027). Na caixa de regressão, os 8 desfoques falsos em
  página com borda preta caíram para zero.
- 1.1.0: `min_ink_coverage` sobe para 0,01, o limite de página quase branca: verso só
  com carimbo ou rubrica não é avaliado por esta regra (a página já vai ao revisor como
  quase branca).
- 1.0.0: versão inicial, normalizada pelo contraste.
