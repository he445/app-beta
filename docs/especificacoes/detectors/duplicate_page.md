# duplicate_page: Página duplicada

Versão: 1.1.0 · Severidade padrão: médio

## Objetivo

Encontrar a mesma folha capturada duas vezes e propor remover uma das vias. Na operação,
duplicata quase nunca é cópia exata: é a mesma folha passada duas vezes no scanner, com
deslocamento, inclinação e exposição um pouco diferentes. Duas vias legítimas existem, por
isso a remoção é sempre só proposta.

## Entrada

Para cada página: raster de análise, máscara e cobertura de tinta, energia de
[`blur`](blur.md) e as marcas de numeração (do `numbering.json` ou lidas da imagem).

## Algoritmo

```text
para cada página:
    dhash ← reduza a 17×16 (média de área); bit = pixel[i][j+1] > pixel[i][j]; 256 bits
    miniatura ← 128 px de largura (média de área), suavizada com gaussiana σ = 1
    vista ← 256 px de largura (média de área)
    máscara ← máscara de tinta reduzida a 512 px de largura
    hash_exato ← hash do raster de análise, se cobertura ≥ blank_threshold da folha branca
    elegível ← cobertura ≥ min_ink_coverage
para cada par (i < j), na ordem do lote:
    se hash_exato_i = hash_exato_j: semelhança ← 1 (cópia exata, sem depender de tinta)
    senão:
        se não elegíveis: pule
        se popcount(dhash_i xor dhash_j) > max_hash_distance: pule
        se correlação das miniaturas (sem alinhar) < candidate_min_similarity: pule
        para cada giro de −3° a +3°, de 0,5° em 0,5°:
            deslocamento ← correlação de fase das vistas (janela de Hann)
            semelhança ← correlação normalizada das vistas suavizadas (σ = 1,5), só na
                         área que se sobrepõe depois do giro e do deslocamento
        fica o melhor alinhamento
        se semelhança < min_similarity: pule
        diferença ← fração do traço de uma máscara sem traço da outra a até 2 px, com o
                    mesmo alinhamento, fora de uma moldura de 4%
        se diferença > max_ink_difference: pule   (formulário repetido, preenchido diferente)
    se as duas páginas têm um número de folha lido com confiança ≥ numbering_veto_confidence
       e os números são diferentes: pule
    cópia ← a segunda ocorrência, se a razão de nitidez for ≥ sharpness_margin;
            senão a menos nítida
    se a cópia já foi sinalizada: pule
    sinaliza a cópia
```

A correlação das miniaturas do filtro grosso é calculada em tamanho fixo, como produto
escalar de vetores normalizados.

**Qual via sai.** Com nitidez parecida, sai a que vem depois no lote. Se uma via for
claramente pior, sai ela, mesmo sendo a primeira; nesse caso, no lote corrigido, a via
que fica ocupa a posição da que saiu (`params.keep_position`), para o documento não sair
de ordem.

**Calibração** (caixa de regressão, [como rodar](../../testes/caixa-de-regressao.md),
`score_box.py --calibrar-duplicata`): os 25 pares verdadeiros ficaram com semelhança de
0,986 a 1 e diferença de tinta de no máximo 0,004; os pares falsos mais parecidos, com
semelhança de no máximo 0,955 (ou diferença de tinta de pelo menos 0,016). Uma
redigitalização sintética de página de texto denso, girada até 3°, e a cópia do caso de
conformidade ficaram entre 0,965 e 0,988. Daí `min_similarity` = 0,96 e
`max_ink_difference` = 0,01. Uma normalização local de brilho antes da correlação foi
testada e descartada: em página limpa ela apaga o sinal fino e derrubava a cópia do caso
de conformidade para 0,92. A correlação normalizada já ignora diferença global de brilho
e contraste entre as passadas.

## Parâmetros

| Nome | Tipo | Padrão |
| --- | --- | --- |
| `max_hash_distance` | inteiro (bits) | 80 |
| `candidate_min_similarity` | número | 0,6 |
| `min_similarity` | número | 0,96 |
| `max_ink_difference` | número | 0,01 |
| `sharpness_margin` | número | 0,8 |
| `numbering_veto_confidence` | número | 0,85 |
| `min_ink_coverage` | número | 0,002 |

## Saída

`measure` = semelhança alinhada; `threshold` = `min_similarity`; correção
`automatic/remove_page` com `params.duplicate_of` = página mantida e, quando sai a
primeira ocorrência do mesmo documento, `params.keep_position` = verdadeiro.

## Falhas conhecidas e casos de borda

- Formulário idêntico com preenchimento muito pequeno (uma rubrica, um número) pode
  passar na diferença de tinta; sem número de folha diferente para vetar, vira par.
- A redigitalização girada mais de 3° não é alinhada e tende a escapar.
- Comparação O(n²) no hash: adequada até alguns milhares de páginas por lote; acima disso,
  indexar o hash por blocos (fase seguinte).
- Numeração repetida da cópia não gera `numbering_review` extra (ver `sequencing.md`).

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0005/0005.tif` (cópia de `0001.tif`); em
`CX001/DOC0009`, dois formulários iguais com preenchimentos diferentes que não podem virar
duplicata.

## Histórico de versões

- 1.0.0: versão inicial.
- 1.1.0: comparação alinhada (giro e deslocamento), segunda checagem pela diferença de
  tinta, veto pela numeração, hash exato do raster e a segunda ocorrência como cópia
  quando a nitidez é parecida (ADR-0026).
