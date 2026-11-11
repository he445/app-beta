# blur: Desfoque

Versão: 1.1.0 · Severidade padrão: crítico

## Objetivo

Encontrar páginas desfocadas, em que a informação pode estar perdida e a única correção
aceitável é redigitalizar.

## Entrada

Raster de análise (cinza, 150 dpi), máscara de tinta e área útil (ver
[`blank_page.md`](blank_page.md#máscara-de-tinta-e-área-útil)).

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

- 1.1.0: `min_ink_coverage` sobe para 0,01, o limite de página quase branca: verso só
  com carimbo ou rubrica não é avaliado por esta regra (a página já vai ao revisor como
  quase branca).
- 1.0.0: versão inicial, normalizada pelo contraste.
