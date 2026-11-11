# Como contribuir

## Definição de pronto

Toda mudança precisa de: código, testes, especificação atualizada, manifesto válido, caso
de conformidade, docstring nas funções públicas e entrada no `CHANGELOG.md`
(ADR-0017). A CI cobra o que é verificável:

| Item | Verificação |
| --- | --- |
| Especificação de cada regra, no modelo, com a mesma versão do manifesto | `tests/test_documentation.py` |
| Manifesto válido | `tests/test_contracts.py` |
| Caso de conformidade de cada regra | `tests/test_documentation.py` |
| Contrato válido e sem quebra sem versão maior | Spectral e oasdiff na CI |
| Docstrings | Ruff (regra D, estilo Google) |
| ADR com Contexto, Decisão e Consequências | `tests/test_documentation.py` |
| Links relativos, referência gerada em dia e documentação só em `docs/` | `tools/docs/check_docs.py` (também em `tests/test_documentation.py`) |
| Site sem aviso | `mkdocs build --strict` na CI |
| Markdown | markdownlint na CI (`.markdownlint-cli2.yaml`) |
| Dependências do domínio | `tests/test_architecture.py` |

Mudança de porta, dependência ou contrato exige ADR no mesmo PR (`docs/adr/0000-template.md`).

## Fluxo

```bash
cd engine
uv sync
uv run pre-commit install        # opcional: roda Ruff e mypy antes de cada commit
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest
```

Na interface (`ui/`): `npm run gen` depois de mudar o contrato, `npm run typecheck`,
`npm test` e o fluxo completo de `ui/e2e/` antes de mudanças visíveis.

- Commits em português, no formato Conventional Commits (`feat(detectors): ...`).
- Código e contrato em inglês; documentação e mensagens em português (ADR-0006).
- Documentação só em `docs/`, descrevendo o sistema como ele é (ADR-0017). Depois de mudar
  o contrato, um manifesto ou a linha de comando: `uv run --project engine python tools/docs/gen_reference.py`.
- Nunca versione lotes de clientes. `.gitignore` já exclui `lote*/`, `saida/` e `data/`.
