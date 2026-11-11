# Rodar a demonstração

Roteiro técnico da demonstração, com a [base sintética](../testes/base-sintetica.md).

## No celular, em 5 minutos

Com a imagem publicada (ver [Publicar a demonstração](publicar-demonstracao.md)), abra o endereço no celular:

1. digite seu nome e toque em **Começar**;
2. toque em **Analisar lote-demonstracao** (33 páginas, 12 documentos);
3. no painel: veredito e **55%** das páginas dispensando revisão;
4. **Sequência → CX001/DOC0001 → Corrigir tudo**: a página torta é endireitada, a branca
   sai, a sem nitidez aparece como "precisa redigitalizar" e a folha 4 faltando pede
   decisão (**Salvar** fica bloqueado até lá);
5. decida a página faltando, toque em **Salvar correções** e mostre o zip baixado.

Perfil `demo`: só página faltando, em branco, torta e sem nitidez (ADR-0010). No lote de
demonstração, os 6 defeitos inseridos são encontrados, sem sinalização a mais.

## Métricas da base completa

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
uv run --project engine qa analyze lote-demo --profile profiles/completo.yaml --out saida
```

## 3. Medir contra o gabarito

```bash
uv run --project engine python tools/synth/evaluate.py saida/report.json lote-demo/gabarito.json
```

Resultado de referência (semente padrão, 199 páginas, contêiner de 4 núcleos sem GPU):

| Métrica | Meta | Obtido |
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
    Os defeitos sintéticos são mais limpos que os reais. A leitura da numeração
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
