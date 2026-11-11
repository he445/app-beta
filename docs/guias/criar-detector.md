# Criar um detector

A definição de pronto (`CONTRIBUTING.md`) vale para cada regra nova; a CI cobra os itens
marcados com ✔.

1. **Especificação** ✔: copie `docs/especificacoes/detectors/_TEMPLATE.md` para `docs/especificacoes/detectors/<id>.md`
   e escreva o algoritmo em pseudocódigo, sem citar bibliotecas. Documente cada parâmetro.
2. **Manifesto** ✔: `engine/src/qa_engine/detectors/<id>/manifest.yaml`, validado contra
   `contracts/schemas/detector-manifest.schema.json`. A versão do manifesto e a da
   especificação têm de ser iguais.
3. **Código**: `engine/src/qa_engine/detectors/<id>/__init__.py` com uma classe que
   implementa `PageDetector` (`measure` e `evaluate`, funções puras) e `DETECTOR = ...`.
4. **Registro**: inclua o id em `RULES` e o detector em `PAGE_DETECTORS`
   (`detectors/registry.py`), e o id no `enum` de `profile.schema.json`.
5. **Testes**: casos em `engine/tests/test_detectors.py`, incluindo uma página limpa que
   não dispara.
6. **Conformidade** ✔: um defeito no plano `conformance_plan()` de `tools/synth/synth.py`
   e o gabarito regenerado em `conformance/expected/core.json`.
7. **Docstrings** ✔ (Ruff, regra D) e entrada no `CHANGELOG.md`.

Regras para o detector:

- compare com a linha de base do lote sempre que possível, não com número fixo;
- toda sinalização traz `measure`, `threshold`, `confidence`, mensagem em português e
  uma correção proposta; nunca proponha [correção proibida](../especificacoes/corrections.md);
- sem aleatoriedade; empates resolvidos por ordem estável.
