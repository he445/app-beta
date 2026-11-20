# 0026: Duplicata com alinhamento e segunda checagem de tinta

Status: aceito · Data: 2026-11-19 · Decisores: Everton Ferreira

## Contexto

Na caixa de regressão de 1.000 páginas, a regra `duplicate_page` 1.0.0 achou 21 de 25
pares, e em 2 marcou o original como cópia. Ela comparava as miniaturas sem alinhar:
deslocar a folha 1 mm na segunda passada derrubava a semelhança para 0,86–0,95, contra o
limite de 0,95. A cópia era a menos nítida, e o ruído da redigitalização aumenta a nitidez
medida. Página com menos de 0,5% de tinta nem entrava na comparação, nem para cópia exata.
Na operação, duplicata quase nunca é cópia exata: é a mesma folha passada duas vezes.

## Opções consideradas

1. Baixar o limite da correlação sem alinhar. Junta formulários parecidos de verdade.
2. Alinhar antes de comparar (giro de ±3° e deslocamento por correlação de fase) e
   confirmar com uma segunda checagem pela tinta, que separa formulário repetido.
3. Comparar descritores de pontos (ORB, SIFT). Mais caro e frágil em página de texto, que
   repete o mesmo padrão em toda parte.

## Decisão

Opção 2 ([especificação](../especificacoes/detectors/duplicate_page.md)). O dHash e a
correlação sem alinhar continuam como filtro grosso (o dHash sobe para 80 bits, porque a
redigitalização girada 3° chega a 72); a comparação alinhada roda só nos candidatos.
A segunda checagem compara as máscaras de tinta a 512 px: o preenchimento de um formulário
some numa escala menor. Números de folha diferentes lidos com confiança vetam o par. A cópia
exata é achada pelo hash do raster, sem depender de tinta. Com nitidez parecida, sai a
segunda ocorrência; se a primeira for claramente pior, sai ela e a outra ocupa a posição
dela no lote corrigido.

A normalização local de brilho proposta para a vista foi testada e descartada: em página
limpa ela apagava o sinal fino (a cópia do caso de conformidade caía de 0,99 para 0,92).
A correlação normalizada já ignora diferença global de brilho e contraste.

## Consequências

- Caixa de regressão: 25 de 25 pares, todos com a cópia certa, e nenhum par falso. A etapa
  de lote não ficou mais lenta (caixa inteira em 222 s, como antes).
- Os limites (0,96 e 0,01) têm folga pequena sobre a redigitalização sintética de texto
  denso (0,965). Se o beta mostrar duplicata escapando, o primeiro ajuste é o
  `min_similarity` da estação.
- A impressão digital de cada página cresce (vista de 256 px e máscara de 512 px, em PNG,
  algumas dezenas de KB por página).
- Formulário repetido com preenchimento mínimo e sem número de folha continua podendo
  virar par; fica como falha conhecida.
- Cobrança: `engine/tests/test_duplicates.py` e o documento `CX001/DOC0009` do lote de
  conformidade.
