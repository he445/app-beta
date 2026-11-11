# 0014: Orientação por classificador ONNX, aplicada como vista em memória

Status: aceito · Data: 2026-11-11 · Decisores: Everton Ferreira

## Contexto

O revisor abre e gira à mão a página que veio de lado ou de cabeça para baixo. A página
de lado também estraga a medida de inclinação, que procura linhas de texto horizontais.

## Opções consideradas

1. Tesseract OSD: precisa de texto impresso suficiente e de um binário externo.
2. Classificador de orientação de página do docTR/OnnxTR (Apache-2.0).
3. PP-LCNet_x1_0_doc_ori (PaddleOCR, Apache-2.0) em ONNX, rodando com ONNX Runtime em
   CPU, sem PaddlePaddle.

## Decisão

Opção 3, atrás da porta `OrientationClassifier` (adaptador
`PaddleOrientationClassifier`). A opção 2 fica como plano B se o PP-LCNet errar demais
na amostra real.

- **Sentido travado por teste:** o rótulo do modelo é o giro horário que a página sofreu;
  a correção gira `(360 − rótulo) mod 360` no sentido horário. Teste de ida e volta exata
  nos três ângulos e teste com o modelo real.
- **Vista em memória:** com a página de lado ou de cabeça para baixo (probabilidade de
  pelo menos `review_threshold`), as regras que dependem do sentido do texto
  (inclinação) são medidas numa vista girada; as demais medem a imagem original. Na cópia
  corrigida, a cadeia canônica recorte → girar → endireitar já existe; rotações em torno
  do centro comutam, então o ângulo medido na vista girada vale na cópia.
- **Três faixas:** acima de `auto_threshold` (0,90), rotação automática no "Corrigir
  tudo"; entre `review_threshold` (0,60) e o automático, rotação sugerida que o revisor
  confere e aplica com C; abaixo, nada.
- **Página quase branca não é classificada** (`min_ink_coverage` 0,01): o carimbo de um
  verso não tem sentido de leitura e o modelo erra nele. Pelo mesmo motivo, inclinação e
  desfoque também deixam de avaliar página quase branca (`skew` e `blur` 1.1.0).

## Consequências

- A suíte de conformidade passa a exigir os modelos baixados (CI baixa com cache);
  sem eles, ela é pulada com o comando para baixar.
- O perfil `demo` desliga a regra (foco da demonstração; o servidor de demonstração não
  tem modelos).
- Meta do beta: zero rotação automática errada; cada rotação automática desfeita pelo
  revisor sobe `auto_threshold`.
