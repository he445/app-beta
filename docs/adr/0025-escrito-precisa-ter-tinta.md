# 0025: Escrito na folha em branco precisa ter tinta

Status: aceito · Data: 2026-11-19 · Decisores: Everton Ferreira

## Contexto

A folha com numeração nunca é branca (ADR-0015): basta o leitor de numeração achar uma
caixa de escrito na região da numeração ou, em página quase vazia, nos quatro cantos. Na
caixa de regressão de 1.000 páginas, nenhuma das 10 folhas em branco com transparência do
verso foi removida: o detector de texto (PP-OCRv5) normaliza o contraste e acha o texto
espelhado do verso, a 4–24 níveis de cinza do papel. Duas folhas brancas com gradiente de
luz também ficaram, porque o plano B por limiar adaptativo devolveu uma caixa do tamanho
da região inteira. Em papel fino de processo, verso transparente é comum.

## Opções consideradas

1. Subir a altura mínima ou o escore mínimo das caixas do detector. Não separa: a
   transparência tem o tamanho e a forma de texto de verdade.
2. Conferir cada caixa contra o papel da página: só conta como escrito a caixa com pixels
   de tinta (`cinza ≤ papel − 40`, o teto da máscara de tinta).
3. A opção 2 com uma classe intermediária: caixa sem tinta, mas com contraste acima da
   transparência, é "traço fraco" e deixa a branca para revisão.

## Decisão

Opção 3 ([especificação](../especificacoes/detectors/blank_page.md)). Sem a classe do
meio, a correção criaria o erro oposto e pior: remover uma folha numerada a lápis claro.
Com ela, a folha vai para revisão, nunca para remoção automática.

Dentro da caixa vale só o teto `papel − 40`, não o Otsu da página inteira, que numa
página com texto impresso fica baixo demais e deixaria de fora a caneta azul. A caixa
classificada como traço fraco ou fundo não é lida pelo reconhecedor: o texto espelhado do
verso também não vira marca de numeração.

## Consequências

- As 30 folhas brancas da caixa de regressão (transparência, gradiente e poeira) passam a
  ser brancas; os parâmetros novos ficam em `blank_page/manifest.yaml`.
- `faint_min_delta` (26) tem pouca folga sobre a transparência medida (24). Se o beta
  mostrar verso mais escuro, o erro cai no lado seguro: branca para revisão.
- Número escrito abaixo de 26 níveis de contraste cai como fundo. É mais claro que o lápis
  do caso de conformidade (30) e fica registrado como falha conhecida.
- Cobrança: casos da folha em branco em `tools/synth/numbering.py` (transparência e lápis
  claro) e testes de unidade da classificação.
