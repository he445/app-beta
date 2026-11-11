# 0001: Interface web e motor Python em servidor, ligados por API

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

Nada pode ser instalado nos computadores da empresa. O processamento precisa de
OpenCV, OCR e ferramentas de PDF, que vivem melhor num servidor. Documentos reais de
clientes não podem sair da empresa (LGPD e cláusulas de confidencialidade).

## Opções consideradas

1. Tudo no navegador (WebAssembly): nada instalado, mas OCR e PDF/A limitados e lentos.
2. Aplicativo desktop: exige instalação, vetado.
3. Interface web estática + motor em contêiner atrás de uma API.

## Decisão

Opção 3. A interface é um site estático e o motor é um contêiner Docker exposto pela API
de `contracts/openapi.yaml`.

- **PoC:** contêiner num serviço de nuvem, só com lotes sintéticos ou públicos, token de
  acesso, CORS restrito ao domínio da interface e apagamento automático em 24 horas.
- **Piloto:** o mesmo contêiner num servidor da rede interna aprovado pela TI.

## Consequências

- Os computadores só precisam do navegador; o mesmo artefato vai da nuvem ao servidor interno.
- O envio de documento real ao servidor da PoC é um risco operacional: mitigado por aviso
  na tela de envio, token, retenção de 24 h (`QA_RETENTION_HOURS`) e lotes de demonstração.
- A opção 1 continua possível no futuro porque o comportamento está no contrato e na
  especificação (ADR-0002, [guia de portabilidade](../guias/portar-linguagem.md)).
