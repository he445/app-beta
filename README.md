# QA Automático de Digitalização

Triagem automática de lotes digitalizados: encontra defeitos de imagem, de sequência e de
completude, propõe uma correção para cada um e entrega ao revisor só o que precisa de olho
humano. O original nunca é alterado e toda decisão é de uma pessoa.

**A documentação fica em [`docs/`](docs/index.md)**: visão geral, instalação, operação,
arquitetura, especificações, referência e testes.

## Começo rápido

```bash
cd engine && uv sync && cd ..
uv run --project engine python tools/synth/synth.py demo --out lote-demo --pages 200
uv run --project engine qa analyze lote-demo --profile profiles/completo.yaml --out saida
```

Passo a passo, interface e Docker: [Instalar e rodar](docs/tutoriais/instalar.md).

## Estrutura

```text
contracts/      fonte da verdade: OpenAPI 3.1 + JSON Schema 2020-12
conformance/    gabarito, tolerâncias e executor que qualquer implementação precisa passar
engine/         motor de referência em Python
ui/             interface web (React + TypeScript + Vite)
profiles/       perfis de cliente
tools/          base sintética, medição de acerto e ferramentas de documentação
deploy/         empacotamento
docs/           documentação (site MkDocs)
```

[Como contribuir](CONTRIBUTING.md) · [Histórico de versões](CHANGELOG.md)
