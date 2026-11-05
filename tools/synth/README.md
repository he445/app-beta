# Base sintética

`synth.py` gera lotes com defeitos inseridos de forma controlada e um gabarito;
`evaluate.py` mede a taxa de acerto de um relatório contra o gabarito (seção 18 do ADD).

```bash
uv run --project engine python tools/synth/synth.py demo --out lote-demo --pages 200
uv run --project engine python tools/synth/synth.py conformance --out conformance/fixtures/core
uv run --project engine python tools/synth/evaluate.py saida/report.json lote-demo/gabarito.json
```

- Páginas: texto pseudo-jurídico em DejaVu Serif, ruído de papel, "Página X de Y" e
  "fls. N"; TIFF com deflate e tags de equipamento, data e operador.
- Estrutura: `CXnnn/DOCnnnn/nnnn.tif` (caixa, documento, página).
- Numeração manuscrita: **simulada** em `numbering.json` no formato do leitor (seção 6),
  com leituras erradas de baixa confiança inseridas de propósito.
- Semente fixa: a mesma linha de comando gera o mesmo gabarito.

Próximo passo previsto no ADD: dígitos manuscritos de bases públicas, números riscados
desenhados na imagem e folhas numeradas à mão pela equipe, para medir o leitor real.
