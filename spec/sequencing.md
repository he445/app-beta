# Sequência e completude

Versão: 1.0.0 · Regras: `missing_page` (crítico), `out_of_order` (médio),
`numbering_review` (alto ou médio), `completeness_unverifiable` (baixo)

## Objetivo

Encontrar páginas faltando, fora de ordem e numeração duvidosa a partir da numeração de
folhas (seção 6 do ADD). Nenhuma leitura isolada é aceita como verdade: o documento
inteiro decide.

## Entrada

Por página, zero ou mais **marcas** (números escritos na região de numeração). Cada marca
tem até três leituras `(texto, confiança)` e um indicador `struck` (riscada). Na PoC as
marcas vêm de `numbering.json` (ver `batch-layout.md`); o leitor de manuscrito
(TrOCR ou PaddleOCR-VL) implementará a porta `NumberingReader` com a mesma saída.

## Folha

`Folha = (número, letra, verso)`, com ordem lexicográfica nessa ordem. Leitura aceita
(expressão regular, sem diferenciar maiúsculas):

```text
^\s*(fls?\.?\s*)?(\d{1,5})(\s*-?\s*[A-UW-Z])?(\s*-?\s*(v|verso))?\s*$
```

Exemplos: `12`, `fls. 12`, `12-A`, `12v`, `12-v`. Forma canônica: `12`, `12-A`, `12v`.

**Sucessor** no modo `simple`: `(n+1)`. No modo `recto_verso`: `(n, letra, verso)` se a
folha é frente; `(n+1)` se é verso. **Intercalação** legítima: mesmo número, letra
maior, sem verso (no modo `recto_verso`, só depois de um verso). **Faltando entre a e b**:
os sucessores de `a` estritamente antes de `b`, se `b > a`, `b ≠ sucessor(a)` e `b` não é
intercalação de `a`.

## Algoritmo

### 0. Duplicatas

A cópia de cada par de [`duplicate_page`](detectors/duplicate_page.md) entra sem marcas:
não participa da sequência, já que a correção proposta é removê-la.

### 1. Ordem proposta

```text
leitura confiável da página ← o topo da única marca não riscada, se confiança ≥ high_confidence
blocos ← cada página com leitura confiável abre um bloco; as seguintes sem leitura
         confiável (versos, por exemplo) entram no bloco aberto
ordem ← páginas antes do primeiro bloco + blocos ordenados de forma estável pela folha
reordenado ← ordem ≠ ordem original (só se houver pelo menos 2 blocos)
```

### 2. Resolução da sequência (Viterbi)

Estado: a folha vigente da página (ou `nada`, enquanto nenhuma é conhecida).
Opções da página `i`:

- cada leitura de cada marca não riscada que seja uma folha válida, com pontuação
  `w_read × confiança`;
- **inferida**: `sucessor(estado anterior)`, com pontuação `w_step − custo`, em que
  `custo = 0` se a página não tem marca e `w_infer` se tem.

Transição de `p` para `c`:

| Caso | Pontuação |
| --- | --- |
| `p = nada` | 0 |
| `c = sucessor(p)` | `+w_step` |
| `c` é intercalação de `p` | `+w_intercalation` |
| `c > p` | `−w_gap × |faltando(p, c)|` |
| `c = p` | `−w_repeat` |
| `c < p` | `−w_back` |

Para cada estado guarda-se só a melhor pontuação; empate fica com a primeira oferta
(leituras na ordem das marcas e das leituras, depois a inferida). No fim escolhe-se o
estado de maior pontuação (empate: maior forma canônica em ordem de texto) e volta-se pelos
ponteiros.

### 3. Estado de cada página

| Condição (na ordem) | Estado |
| --- | --- |
| sem marcas | `absent` |
| ≥ 2 marcas não riscadas com topo ≥ `min_confidence` e textos diferentes | `ambiguous` |
| nenhuma marca não riscada com topo ≥ `min_confidence` | `illegible` |
| escolhida a opção inferida, ou o valor difere do topo da única marca | `inferred` |
| há marca riscada | `renumbered` (`previous` = topos riscados) |
| senão | `read` |

### 4. Lacunas e repetições

Percorre as páginas com valor, na ordem proposta. Uma lacuna entre `a` e `b` é
**confirmada** quando `b` é `read`/`renumbered` com confiança ≥ `high_confidence` e há
uma âncora confiável antes dela: a última página com valor foi confiável, ou, no modo
`recto_verso`, só houve versos `absent` desde a última página confiável. Valor igual ao
anterior é **repetição**.

## Sinalizações

| Regra | Alvo | Quando | Severidade | Correção |
| --- | --- | --- | --- | --- |
| `out_of_order` | documento | reordenado | médio | `automatic/reorder`, `params.order` |
| `missing_page` | documento | lacuna confirmada | crítico | `physical/locate_sheet` (`rescan_back` se só faltam versos) |
| `missing_page` | documento | páginas < contagem do `manifest.csv` | crítico | `physical/locate_sheet` |
| `numbering_review` | página | lacuna não confirmada (página depois da lacuna) | alto | `escalate/human_review` |
| `numbering_review` | página | repetição, salvo se a página está num par de `duplicate_page` | alto | idem |
| `numbering_review` | página | `ambiguous` ou `illegible` | alto | idem |
| `numbering_review` | página | `inferred` | médio | idem |
| `completeness_unverifiable` | documento | nenhuma página com marca e sem contagem declarada | baixo | `escalate/human_review` |

Uma dúvida nunca vira "página faltando": vira `numbering_review`.

## Parâmetros (perfil, seção `numbering`)

| Nome | Padrão | | Nome | Padrão |
| --- | --- | --- | --- | --- |
| `mode` | `simple` | | `w_step` | 2,0 |
| `min_confidence` | 0,5 | | `w_intercalation` | 1,0 |
| `high_confidence` | 0,85 | | `w_gap` | 1,0 |
| `w_read` | 4,0 | | `w_back` | 4,0 |
| `w_infer` | 1,0 | | `w_repeat` | 1,0 |

Os pesos fazem uma leitura confiável (≥ 0,5) vencer a inferência numa lacuna de uma folha
(`4c − 1 > 2 − 1`) e uma leitura errada isolada perder para o contexto.

## Falhas conhecidas

- Volume que recomeça em 1 aparece como fora de ordem; regra de reinício no perfil é
  fase seguinte.
- A trilha de numeração anterior (riscada) é registrada, mas não resolvida por uma
  segunda programação dinâmica.
- Numeração impressa ("Página 3 de 12") depende da porta `OcrEngine` (fase seguinte).

## Casos de conformidade

`conformance/fixtures/sequencing/*.json` (entrada e saída esperada do resolvedor) e
`conformance/fixtures/core` (documentos `DOC0004`, `DOC0005`, `DOC0006`).

## Histórico de versões

- 1.0.0: versão inicial.
