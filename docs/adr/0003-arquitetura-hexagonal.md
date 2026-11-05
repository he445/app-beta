# 0003: Arquitetura hexagonal, núcleo sem entrada e saída

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

Portar significa reescrever o núcleo e escolher adaptadores equivalentes (seção 16).
Detectores precisam ser testáveis isoladamente e trocáveis um a um.

## Decisão

Camadas em `engine/src/qa_engine/`, com dependência sempre apontando para dentro:

| Camada | Pode depender de |
| --- | --- |
| `domain` | só da linguagem (sem NumPy) |
| `detectors` | `domain`, NumPy e OpenCV; uma função pura por defeito |
| `ports` | `domain` (interfaces `Protocol`) |
| `application` | `domain`, `detectors`, `ports` |
| `adapters` | `ports` e a ferramenta que embrulham |
| `entrypoints` | `application` |

Detectores de página têm duas fases (`measure` por página, `evaluate` contra a linha de
base do lote) para comparar com a mediana do próprio lote.

## Consequências

- `domain` e `detectors` são testados sem disco, rede nem relógio.
- `application/services.py` é a única raiz de composição que conhece os adaptadores.
- O teste `test_architecture.py` falha se `domain` importar algo de fora.
