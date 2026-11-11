# blank_page: Página em branco

Versão: 1.0.0 · Severidade padrão: baixo

## Objetivo

Marcar páginas em branco para remoção conforme o perfil, sem nunca remover versos com
carimbo, rubrica ou assinatura.

## Entrada

Raster de análise.

## Máscara de tinta e área útil

Compartilhadas por todos os detectores de página.

```text
papel ← percentil 90 do cinza da página
limiar ← min(Otsu(cinza), papel − 40)
tinta_bruta ← cinza ≤ limiar      (o limiar de Otsu pertence à classe escura)
tinta ← tinta_bruta sem componentes conexos (vizinhança 8) com menos de 6 pixels
m ← arredondar(0,04 × min(altura, largura))
área_útil ← linhas [m, altura − m), colunas [m, largura − m)
cobertura ← fração de tinta na área útil
```

O teto `papel − 40` impede que o Otsu de uma página branca separe o próprio ruído do papel.

## Algoritmo

```text
maior_marca ← área do maior componente conexo de tinta na área útil
se cobertura < blank_threshold e maior_marca < mark_min_area:
    branca; correção automatic/remove_page se remove_blank_pages, senão escalate
senão se cobertura < near_blank_threshold:
    quase branca; correção escalate/human_review (nunca removida automaticamente)
```

Confiança: branca `limitar(1 − 0,5 × cobertura / blank_threshold)`; quase branca 0,5.

## Parâmetros

| Nome | Tipo | Padrão | Faixa |
| --- | --- | --- | --- |
| `blank_threshold` | número | 0,003 | 0 a 1 |
| `near_blank_threshold` | número | 0,01 | 0 a 1 |
| `mark_min_area` | inteiro (px a 150 dpi) | 400 | ≥ 0 |
| `remove_blank_pages` | booleano | verdadeiro | — |

## Saída

`measure` = cobertura; `threshold` = limiar que decidiu.

## Falhas conhecidas e casos de borda

- "Página intencionalmente deixada em branco" depende de OCR (porta `OcrEngine`, fase
  seguinte); hoje a frase vira tinta e a página fica quase branca ou normal.
- Documento pequeno (recibo) em página grande: a detecção do contorno do papel é fase
  seguinte.

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0002/0005.tif`.

## Histórico de versões

- 1.0.0: versão inicial.
