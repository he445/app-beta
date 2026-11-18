# 0023: Limiar de confiança alta por origem da numeração

Status: aceito · Data: 2026-11-18 · Decisores: Everton Ferreira

## Contexto

O relatório de testes de 18/11/2026 pediu calibrar a confiança do PP-OCRv5 até a faixa
acima de `high_confidence` (0,85) errar no máximo 1%. Medida no ARDIS, a confiança já é
razoavelmente calibrada (erro de calibração esperado de 0,035), e a faixa acima de 0,85
erra 1,8%: o limiar é que estava baixo para a meta. O mesmo `high_confidence` vale para o
`numbering.json`, cujas marcas vêm de outro leitor, com outra escala, e nas quais a suíte
de conformidade foi construída (confiança de 0,88 a 0,99).

## Opções consideradas

1. Calibrar (temperatura ou isotônica) e manter 0,85.
2. Subir `high_confidence` no perfil.
3. Limiar próprio para as marcas lidas da imagem (`numbering.image_high_confidence`).

## Decisão

Opção 3, com 0,98 no `sos-piloto`. A opção 1 piora: a calibração sobe as faixas de 0,70
a 0,95, que acertam mais do que dizem, e mais leituras passam de 0,85. A opção 2 muda também o
`numbering.json` e a conformidade, que não vêm do PP-OCR.

## Consequências

- Acima de 0,98, o erro medido é 0,69% (intervalo de 95% de 0,27% a 1,75%; 0,91% fora da
  amostra em validação cruzada), cobrindo 38% das leituras (antes, 73% acima de 0,85).
- Menos leituras ancoram lacunas: mais lacunas viram `numbering_review` em vez de
  `missing_page`, e menos ordens são propostas pela numeração. Leitura errada com
  confiança entre 0,85 e 0,98 deixa de confirmar página faltando.
- O limiar foi medido em datas suecas; refazer com as páginas reais anotadas no beta.
