# Rodar a demonstração

Roteiro técnico da seção 20 do ADD, com a base sintética.

## 1. Gerar o lote

```bash
uv run --project engine python tools/synth/synth.py demo --out lote-demo --pages 200
```

Cerca de 25% das páginas recebem defeitos com parâmetros conhecidos (desfoque,
inclinação, bordas, escurecimento, desbotamento, baixa resolução, página removida,
páginas trocadas, duplicada, branca, leitura de numeração errada, arquivo truncado).
`lote-demo/gabarito.json` lista cada um; `numbering.json` simula a saída do leitor de
numeração manuscrita.

## 2. Analisar

```bash
uv run --project engine qa analyze lote-demo --profile profiles/demo.yaml --out saida
```

## 3. Medir contra o gabarito

```bash
uv run --project engine python tools/synth/evaluate.py saida/report.json lote-demo/gabarito.json
```

Resultado de referência (semente padrão, 199 páginas, contêiner de 4 núcleos sem GPU):

| Métrica | Meta (seção 18) | Obtido |
| --- | --- | --- |
| Defeitos críticos encontrados | ≥ 98% | 100% |
| Todos os defeitos encontrados | ≥ 95% | 100% |
| Precisão por sinalização | ≥ 70% | 88,7% |
| Páginas que dispensam revisão | ≥ 50% | 67,3% |
| Página faltando encontrada | ≥ 95% | 100% |
| Velocidade | ≥ 3 p/s | ~7 p/s (A4, 300 dpi, sem leitura de manuscrito) |

As 6 sinalizações "extras" são `exposure` em páginas desfocadas ou de baixa resolução,
que de fato perderam contraste; a precisão por alvo é 100%.

!!! warning "Números sintéticos são um teto"
    Os defeitos sintéticos são mais limpos que os reais (seção 19). A leitura da numeração
    manuscrita está simulada. Só o piloto com lotes reais já conferidos decide.

## 4. Pela API

```bash
TOKEN=troque-isto
curl -H "Authorization: Bearer $TOKEN" -F profile_id=demo -F files=@lote-demo.zip \
     http://localhost:8000/batches
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:8000/batches/<id>/events
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/batches/<id>/findings?severity=critical"
curl -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"action": "correct", "reviewer": "garantidor1"}' \
     http://localhost:8000/findings/<finding_id>/decision
```
