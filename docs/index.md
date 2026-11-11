# QA Automático de Digitalização

Triagem automática de lotes digitalizados: encontra defeitos de imagem, de sequência e de
completude, propõe uma correção para cada um, extrai os metadados do Decreto 10.278/2020
e entrega ao revisor só o que precisa de olho humano.

## Por onde começar

| Você é | Comece por |
| --- | --- |
| **TI avaliando o sistema** | [Visão geral](visao-geral/index.md), [Segurança e privacidade](seguranca-e-privacidade/index.md), [Licenças de terceiros](seguranca-e-privacidade/licencas.md) e [Arquitetura](arquitetura/index.md) |
| **Desenvolvimento** | [Instalar e rodar](tutoriais/instalar.md), [Arquitetura](arquitetura/index.md), [Especificações](especificacoes/index.md), [Testes](testes/index.md) e os [guias](guias/criar-detector.md) |
| **Operação (garantidor, conferente)** | [Interface de revisão](operacao/interface.md) |
| **Gestão** | [Visão geral](visao-geral/index.md) e [Demonstração](guias/demonstracao.md) |

## Onde está cada coisa

| Pasta | Conteúdo |
| --- | --- |
| [Visão geral](visao-geral/index.md) | O que o sistema faz, o problema que resolve, escopo, [princípios](visao-geral/principios.md) e [casos de borda](visao-geral/casos-de-borda.md) |
| [Tutoriais](tutoriais/instalar.md) | Primeiro uso, passo a passo |
| Guias | [Demonstração](guias/demonstracao.md), [publicar a demonstração](guias/publicar-demonstracao.md), [criar uma regra](guias/criar-detector.md), [portar para outra linguagem](guias/portar-linguagem.md), [desenvolver a interface](guias/desenvolver-interface.md) |
| [Operação](operacao/index.md) | Manual de quem usa o programa |
| [Arquitetura](arquitetura/index.md) | Visão arc42, [diagramas C4](arquitetura/c4.md) e decisões ([ADRs](adr/0001-web-app-e-motor-em-servidor.md)) |
| [Especificações](especificacoes/index.md) | O comportamento exato de cada regra, da sequência, das correções, da pontuação e dos metadados |
| Referência | [API](referencia/api.md), [perfis](referencia/perfis.md), [linha de comando](referencia/cli.md) e [código](referencia/codigo.md) |
| [Modelos](modelos/index.md) | Ficha de cada modelo de aprendizado de máquina embarcado |
| [Segurança e privacidade](seguranca-e-privacidade/index.md) | Dados guardados, acesso e [licenças de terceiros](seguranca-e-privacidade/licencas.md) |
| [Testes](testes/index.md) | Estratégia, [suíte de conformidade](testes/conformidade.md) e [base sintética](testes/base-sintetica.md) |
| [Glossário](glossario.md) | Termos do domínio e o nome de cada um no código |

O histórico de versões está no `CHANGELOG.md`, na raiz do repositório.
