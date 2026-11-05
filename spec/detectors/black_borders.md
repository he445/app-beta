# black_borders: Bordas pretas

Versão: 1.0.0 · Severidade padrão: baixo

## Objetivo

Encontrar faixas escuras contínuas nas margens (fundo do scanner) e propor recorte.

## Entrada

Raster de análise.

## Algoritmo

```text
escuro ← cinza < dark_level
linha_escura[i] ← fração de escuro na linha i ≥ dark_fraction   (idem coluna_escura)
para cada lado (topo, base, esquerda, direita):
    faixa ← quantidade de linhas/colunas escuras consecutivas a partir da borda,
            examinando no máximo 1/4 da dimensão
    fração[lado] ← faixa / dimensão perpendicular
medida ← max(fração)
sinaliza se medida > min_fraction
região ← retângulo da maior faixa (empate: topo, base, esquerda, direita)
```

Confiança: `limitar(0,6 + medida / (4 × min_fraction))`.

## Parâmetros

| Nome | Tipo | Padrão | Faixa |
| --- | --- | --- | --- |
| `min_fraction` | número | 0,01 | 0 a 1 |
| `dark_level` | inteiro | 70 | 0 a 255 |
| `dark_fraction` | número | 0,9 | 0 a 1 |

## Saída

`measure` = maior fração; `region` = faixa; correção `automatic/autocrop` com
`params.crop_fraction = {top, bottom, left, right}` (frações da dimensão, 4 casas).

## Falhas conhecidas e casos de borda

- Tarja de anonimização encostada na margem pode ser confundida com borda; a regra de
  tarja (retângulo sólido de borda reta) é fase seguinte.
- Borda irregular (folha torta) que não ocupa 90% da linha não é detectada.

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0002/0003.tif`.

## Histórico de versões

- 1.0.0: versão inicial.
