# Suíte de conformidade

Qualquer implementação do motor, em qualquer linguagem, só substitui outra quando passa
**100%** desta suíte ([guia de portabilidade](../guias/portar-linguagem.md)).

| Caminho | Conteúdo | Versionado |
| --- | --- | --- |
| `expected/core.json` | Gabarito do lote `core`: cada defeito inserido, com parâmetros | sim |
| `fixtures/sequencing/cases.json` | Entrada e saída esperada do resolvedor de numeração | sim |
| `fixtures/core/` | Lote `core` (30 páginas TIFF A5, 300 dpi) | **não**: gerado |
| `tolerances.yaml` | Tolerâncias de medida e coocorrências aceitas | sim |
| `run.py` | Executor da implementação de referência | sim |

A suíte usa o perfil `profiles/completo.yaml` (todas as regras); o perfil `demo` liga só
os casos da demonstração (ADR-0010).

## Por que o lote `core` é gerado e não versionado

As páginas têm ruído de papel, que não comprime: o lote ocupa ~58 MB. Ele é gerado de
forma determinística por `tools/synth` (semente fixa) e o teste confere que o gabarito
gerado é **idêntico** a `expected/core.json`. Se o gerador mudar, o teste falha até o
gabarito ser atualizado conscientemente no mesmo PR.

```bash
uv run --project engine python tools/synth/synth.py conformance --out conformance/fixtures/core
uv run --project engine qa analyze conformance/fixtures/core --profile profiles/completo.yaml --out /tmp/core-out
uv run --project engine python conformance/run.py /tmp/core-out/report.json
```

`engine/tests/test_conformance.py` faz os três passos (reaproveitando o lote se já existir).

## Procedimento de comparação (para executores em outras linguagens)

1. Para cada sinalização do relatório, monte a chave `(alvo, regra)`: alvo de página é
   `arquivo#n`; alvo de documento é o nome do documento.
2. Para cada defeito do gabarito, os alvos aceitos são `file#page_in_file` mais
   `alternatives` (ou `document`). Pelo menos uma chave precisa existir. Se a regra tem
   entrada em `measures`, compare o campo com a tolerância (`abs` ou `rel`).
3. Chaves aceitas: as encontradas no passo 2 e, nos mesmos alvos, as regras de
   `co_occurrence` da regra esperada.
4. Toda chave do relatório fora das aceitas é divergência.

Para `fixtures/sequencing/cases.json`, compare estados, valores canônicos, ordem
(índices da entrada), lacunas e o conjunto de regras disparadas.
