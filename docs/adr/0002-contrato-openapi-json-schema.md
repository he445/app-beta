# 0002: OpenAPI 3.1 + JSON Schema 2020-12 como fonte da verdade

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

O motor precisa poder ser reimplementado em outra linguagem sem mudar o sistema
(princípio 6). Interface, linha de comando e sistemas futuros falam com o motor.

## Opções consideradas

1. Protobuf + gRPC: tipado e rápido, mas pior para navegador e para leitura humana.
2. OpenAPI 3.1 com JSON Schema 2020-12 em arquivos separados.
3. Modelos Python como fonte (FastAPI gera o OpenAPI).

## Decisão

Opção 2. `contracts/schemas/*.schema.json` define as entidades; `contracts/openapi.yaml`
define as rotas e referencia os esquemas. Protobuf foi avaliado e adiado para quando
houver gRPC.

Na implementação de referência, corpos de requisição e resposta são **validados em tempo
de execução contra os esquemas** (`qa_engine.application.contracts`), e os testes validam
cada resposta da API e cada `report.json`. A geração de modelos Pydantic e de tipos
TypeScript (datamodel-code-generator, openapi-typescript) entra quando a interface for
criada, sem mudar o contrato.

## Consequências

- Uma divergência entre código e contrato quebra os testes, não a produção.
- Mudança de contrato exige versão SemVer; o oasdiff na CI bloqueia quebra sem versão maior.
- A API do FastAPI em `/openapi.json` é gerada do código e serve só como conveniência; a
  referência publicada é `contracts/openapi.yaml`.
