# duplicate_page: Página duplicada

Versão: 1.0.0 · Severidade padrão: médio

## Objetivo

Encontrar a mesma folha capturada duas vezes e propor remover a cópia de pior qualidade.
Duas vias legítimas existem, por isso a remoção é sempre só proposta.

## Entrada

Para cada página: raster de análise, cobertura de tinta e energia de [`blur`](blur.md).

## Algoritmo

```text
para cada página:
    dhash ← reduza a 17×16 (média de área); bit = pixel[i][j+1] > pixel[i][j]; 256 bits
    miniatura ← reduza a 128 px de largura (média de área) e suavize com gaussiana σ = 1
    elegível ← cobertura ≥ min_ink_coverage
para cada par (i < j) de páginas elegíveis, na ordem do lote:
    se popcount(dhash_i xor dhash_j) > max_hash_distance: pule
    semelhança ← correlação cruzada normalizada das miniaturas
    se semelhança < min_similarity: pule
    cópia ← a de menor energia de nitidez (empate: a que vem depois)
    se a cópia já foi sinalizada: pule
    sinaliza a cópia
```

## Parâmetros

| Nome | Tipo | Padrão |
| --- | --- | --- |
| `max_hash_distance` | inteiro (bits) | 48 |
| `min_similarity` | número | 0,95 |
| `min_ink_coverage` | número | 0,005 |

## Saída

`measure` = semelhança; `threshold` = `min_similarity`; correção
`automatic/remove_page` com `params.duplicate_of` = página mantida.

## Falhas conhecidas e casos de borda

- Formulários idênticos com preenchimento diferente podem chegar perto do limiar.
- Comparação O(n²) no hash: adequada até alguns milhares de páginas por lote; acima disso,
  indexar o hash por blocos (fase seguinte).
- Numeração repetida da cópia não gera `numbering_review` extra (ver `sequencing.md`).

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0005/0005.tif` (cópia de `0001.tif`).

## Histórico de versões

- 1.0.0: versão inicial.
