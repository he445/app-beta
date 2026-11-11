# exposure: Escura, clara ou sem contraste

Versão: 1.0.0 · Severidade padrão: alto

## Objetivo

Encontrar páginas escuras, claras demais ou sem contraste, comparando com o "normal" do
próprio lote (papel amarelado ou carbono têm outro normal).

## Entrada

Raster de análise e máscara de tinta.

## Algoritmo

```text
se pixels de tinta < min_ink_pixels: inelegível
papel ← percentil 90 do cinza
contraste ← papel − mediana(cinza nos pixels de tinta)

avaliação (para papel e contraste, separadamente):
se o lote tem ≥ min_batch_size páginas elegíveis:
    centro ← mediana do lote; σ ← max(σ robusto do lote, min_sigma_<medida>)
senão:
    centro ← reference_<medida>; σ ← min_sigma_<medida>
z_papel ← (papel − centro) / σ ;  z_contraste ← (contraste − centro) / σ
sem_contraste ← z_contraste < −z_threshold
sinaliza se |z_papel| > z_threshold ou sem_contraste
medida ← max(|z_papel|, −z_contraste)
```

Correção: sem contraste → `physical/rescan` ("clarear página ilegível" é correção
proibida); escura ou clara com contraste preservado → `automatic/auto_levels`.
Confiança: `limitar(0,5 + (medida − z_threshold) / (2 × z_threshold))`.

O papel (percentil 90) e o contraste papel-tinta não dependem da quantidade de texto,
ao contrário da média e do desvio do histograma, que variam com ela.

## Parâmetros

| Nome | Tipo | Padrão |
| --- | --- | --- |
| `z_threshold` | número | 2,0 |
| `min_batch_size` | inteiro | 5 |
| `min_ink_pixels` | inteiro | 500 |
| `min_sigma_paper` | número | 8 |
| `min_sigma_contrast` | número | 15 |
| `reference_paper` | número | 240 |
| `reference_contrast` | número | 190 |

## Saída

`measure` = maior |z|; `threshold` = `z_threshold`.

## Falhas conhecidas e casos de borda

- Papel térmico desbotado é defeito de origem: o revisor marca "O".
- Desfoque reduz o contraste medido; coocorrência com [`blur`](blur.md) é aceita.

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0003/0002.tif` (escura), `CX001/DOC0003/0003.tif`
(desbotada).

## Histórico de versões

- 1.0.0: versão inicial.
