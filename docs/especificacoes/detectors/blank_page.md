# blank_page: Página em branco

Versão: 1.1.0 · Severidade padrão: baixo

## Objetivo

Marcar páginas em branco para remoção conforme o perfil, sem nunca remover versos com
carimbo, rubrica, assinatura ou numeração. **Folha em branco é a que não tem numeração
nem nenhum conteúdo**: folha com numeração nunca é branca, mesmo que o resto esteja
vazio (um verso numerado, por exemplo); ela fica no lote e conta na sequência.

## Entrada

Raster de análise e, da numeração da página, se há **algum escrito** (`escrito`):

- marcas do `numbering.json` do lote para a página, se houver; ou
- qualquer escrito na região da numeração achado pelo leitor por imagem
  ([numeração lida da imagem](../numeracao-por-imagem.md)), inclusive número riscado
  (riscado ainda é conteúdo) ou ilegível; e
- com os modelos disponíveis, em página quase vazia (`cobertura < near_blank_threshold`),
  qualquer escrito em um dos **quatro cantos** da página original (frações
  `[0,60; 0; 1; 0,18]`, `[0; 0; 0,40; 0,18]`, `[0,60; 0,82; 1; 1]`, `[0; 0,82; 0,40; 1]`):
  em página quase vazia a orientação não é confiável. Valem caixas com altura de pelo
  menos `numbering.min_height_mm`, no máximo 5 alturas de largura e afastadas mais de
  1% do lado menor da borda da página (sombra e borda do digitalizador não são escrito).

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
se escrito:
    nada (a folha tem numeração)
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

Os cinco casos da folha em branco (`tools/synth/numbering.py brancas`): só com número,
só com número riscado e só com número de cabeça para baixo não são sinalizadas; só com
carimbo fica "quase branca" para revisão; totalmente vazia é branca.

## Histórico de versões

- 1.0.0: versão inicial.
- 1.1.0: folha com numeração (do `numbering.json` ou qualquer escrito achado na região
  ou, em página quase vazia, nos quatro cantos) nunca é branca nem quase branca.
