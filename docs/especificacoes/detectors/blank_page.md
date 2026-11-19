# blank_page: Página em branco

Versão: 1.2.0 · Severidade padrão: baixo

## Objetivo

Marcar páginas em branco para remoção conforme o perfil, sem nunca remover versos com
carimbo, rubrica, assinatura ou numeração. **Folha em branco é a que não tem numeração
nem nenhum conteúdo**: folha com numeração nunca é branca, mesmo que o resto esteja
vazio (um verso numerado, por exemplo); ela fica no lote e conta na sequência.

## Entrada

Raster de análise e, da numeração da página, se há **algum escrito** (`escrito`) e se há
**traço fraco** (`traço_fraco`):

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

### Escrito precisa ter tinta

O detector de texto normaliza o contraste e acha "texto" também na transparência do verso
e no gradiente de luz do papel. Por isso cada caixa achada (na região da numeração e nos
cantos) é conferida contra o papel da página antes de contar:

```text
pixels_de_tinta ← pixels da caixa com cinza ≤ papel − 40   (o teto da máscara de tinta)
contraste ← papel − percentil 5 do cinza da caixa
se pixels_de_tinta ≥ writing_min_pixels e pixels_de_tinta / área ≥ writing_min_ink:
    escrito       (a folha tem conteúdo; a caixa segue para a leitura do número)
senão se contraste ≥ faint_min_delta:
    traço fraco   (possível número a lápis claro; a caixa não é lida)
senão:
    fundo         (ignorada)
```

Dentro da caixa vale só o teto `papel − 40`, não o Otsu da página inteira: numa página
com texto impresso o Otsu fica baixo e deixaria de fora a caneta azul. Como a máscara de
tinta é `cinza ≤ min(Otsu, papel − 40)`, todo pixel dela também conta aqui.

`faint_min_delta` foi calibrado na caixa de regressão
([caixa de regressão](../../testes/caixa-de-regressao.md)): a transparência do verso ficou
entre 4 e 24 níveis de contraste e a tinta real das páginas a partir de 92 (percentil 10);
o padrão 26 fica acima da transparência e abaixo do lápis claro de 30 níveis do caso de
conformidade.

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
    se traço_fraco:
        branca para revisão; correção escalate/human_review, confiança 0,5
    senão:
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
| `writing_min_ink` | número | 0,01 | 0 a 1 |
| `writing_min_pixels` | inteiro (px a 150 dpi) | 30 | ≥ 0 |
| `faint_min_delta` | número (níveis de cinza) | 26 | 0 a 255 |
| `remove_blank_pages` | booleano | verdadeiro | — |

## Saída

`measure` = cobertura; `threshold` = limiar que decidiu.

## Falhas conhecidas e casos de borda

- Número a lápis muito claro, abaixo de `faint_min_delta`, cai como fundo e a folha é
  removida. Acima dele, a folha vai para revisão, nunca para remoção automática.

- "Página intencionalmente deixada em branco" depende de OCR (porta `OcrEngine`, fase
  seguinte); hoje a frase vira tinta e a página fica quase branca ou normal.
- Documento pequeno (recibo) em página grande: a detecção do contorno do papel é fase
  seguinte.

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0002/0005.tif`.

Os sete casos da folha em branco (`tools/synth/numbering.py brancas`): só com número,
só com número riscado e só com número de cabeça para baixo não são sinalizadas; só com
carimbo fica "quase branca" para revisão; totalmente vazia e com transparência do verso
são brancas (removidas); com número a lápis claro (30 níveis de contraste) é branca para
revisão.

## Histórico de versões

- 1.0.0: versão inicial.
- 1.1.0: folha com numeração (do `numbering.json` ou qualquer escrito achado na região
  ou, em página quase vazia, nos quatro cantos) nunca é branca nem quase branca.
- 1.2.0: escrito precisa ter tinta (ADR-0025); a caixa sem tinta é traço fraco (branca
  para revisão) ou fundo (ignorada). Parâmetros `writing_min_ink`, `writing_min_pixels`
  e `faint_min_delta`.
