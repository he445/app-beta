# QA Automático de Digitalização

Prova de conceito de uma triagem automática que reduz em pelo menos 50% as páginas que
exigem olho humano, sem deixar passar defeitos críticos. O documento de decisão de
arquitetura completo está em [ADD](add.md).

## Onde está cada coisa

| Para | Leia |
| --- | --- |
| Instalar, rodar a CLI, a API e o Docker | [Instalar](guides/instalar.md) |
| Repetir a demonstração e medir a taxa de acerto | [Demonstração](guides/demonstracao.md) |
| Entender a arquitetura | [C4](architecture/c4.md) e [ADRs](adr/0001-web-app-e-motor-em-servidor.md) |
| Saber exatamente o que cada regra faz | [Especificação](https://github.com/he445/prova-de-conceito/tree/main/spec) |
| Criar um detector | [Guia](guides/criar-detector.md) |
| Portar para outra linguagem | [Guia](guides/portar-linguagem.md) |
| Rotas da API | [Referência da API](reference/api.md) |
| Termos | [Glossário](glossary.md) |

## Estado do incremento atual

Feito: motor de referência (12 regras), API HTTP, linha de comando, contrato, especificação,
suíte de conformidade, base sintética com medição de acerto, Docker e CI.

Próximo: interface web (React + TypeScript, telas da seção 12), leitor de numeração
manuscrita (TrOCR ou PaddleOCR-VL atrás da porta `NumberingReader`), OCR (orientação,
espelhamento, legibilidade, índice), validação PDF/A com veraPDF e gravação de XMP.
