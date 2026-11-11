# Base sintética

`synth.py` gera lotes com defeitos inseridos de forma controlada e um gabarito;
`evaluate.py` mede a taxa de acerto de um relatório contra o gabarito.

```bash
uv run --project engine python tools/synth/synth.py demo --out lote-demo --pages 200
uv run --project engine python tools/synth/synth.py conformance --out conformance/fixtures/core
uv run --project engine python tools/synth/synth.py showcase --out demo/lote-demonstracao
uv run --project engine python tools/synth/evaluate.py saida/report.json lote-demo/gabarito.json
```

- Páginas: texto pseudo-jurídico em DejaVu Serif, ruído de papel, "Página X de Y" e
  "fls. N"; TIFF com deflate e tags de equipamento, data e operador.
- Estrutura: `CXnnn/DOCnnnn/nnnn.tif` (caixa, documento, página).
- Modos: `selftest` (7 páginas A6 com página torta, faltando, em branco e sem nitidez;
  vai dentro do pacote Windows para o teste de fumaça), `demo` (aleatório, todos os
  defeitos, para métricas com o perfil `completo`),
  `conformance` (lote fixo da suíte) e `showcase` (lote da demonstração: os quatro casos
  em foco no mesmo documento, mais documentos limpos; gerado no build da imagem).
- Numeração manuscrita: **simulada** em `numbering.json` no formato do leitor ([sequência](../especificacoes/sequencing.md)),
  com leituras erradas de baixa confiança inseridas de propósito.
- Semente fixa: a mesma linha de comando gera o mesmo gabarito.
- Fontes: DejaVu em `/usr/share/fonts`; em outro sistema, aponte `QA_SYNTH_FONT_DIR` para a
  pasta `ttf` do pacote de fontes.

Próximo passo: dígitos manuscritos de bases públicas, números riscados
desenhados na imagem e folhas numeradas à mão pela equipe, para medir o leitor real.
