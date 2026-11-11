# Arquitetura

Visão no formato [arc42](https://arc42.org/overview). Os diagramas estão em
[C4](c4.md) e as decisões nos ADRs (lista ao lado).

## 1. Objetivos

Reduzir em pelo menos metade as páginas que exigem olho humano, sem deixar passar defeito
crítico ([visão geral](../visao-geral/index.md)). Qualidades que mandam no desenho:
o original nunca é alterado, toda sinalização se explica, e o comportamento é definido
fora do código para que o motor possa ser reescrito sem mudar o sistema
([princípios](../visao-geral/principios.md)).

## 2. Restrições

- Dado de cliente não sai da empresa.
- Sem GPU: o motor roda em CPU comum.
- Nenhuma dependência GPL ou AGPL ligada ao processo do motor
  ([licenças](../seguranca-e-privacidade/licencas.md), ADR-0004).
- Código em inglês, documentação em português (ADR-0006).

## 3. Contexto

Quem usa e o que entra e sai: [diagrama de contexto](c4.md#contexto).

## 4. Estratégia de solução

- **Arquitetura hexagonal** (ADR-0003): o domínio não conhece ferramenta nenhuma; cada
  ferramenta fica atrás de uma porta e pode ser trocada.
- **Contrato primeiro** (ADR-0002): OpenAPI 3.1 e JSON Schema em `contracts/` são a fonte
  da verdade; a interface gera os tipos dela a partir do contrato.
- **Especificação independente de linguagem** e **suíte de conformidade** (ADR-0007):
  qualquer implementação que passe 100% da suíte substitui a de referência.
- **Limiar em perfil**: cada regra tem um manifesto com os padrões, e o perfil do cliente
  os sobrescreve.
- **Configuração em camadas** (ADR-0012): o que descreve o computador fica em TOML,
  validado por esquema, com as variáveis `QA_*` como uma das camadas.

## 5. Blocos de construção

| Camada | Responsabilidade | Pode depender de |
| --- | --- | --- |
| `domain` | Entidades, severidade, resolvedor de sequência, pontuação e veredito | Só a linguagem |
| `detectors` | Uma regra por defeito: `measure` (por página) e `evaluate` (contra o lote) | Domínio, portas e matrizes (NumPy, OpenCV) |
| `application` | Casos de uso: analisar lote, decidir, corrigir, lote corrigido, exportar | Domínio, detectores e portas |
| `ports` | Interfaces: `ImageSource`, `MetadataReader`, `NumberingReader`, `Executor`, `Clock`, `ReviewStore`, `PageVersionStore`, `CorrectedBatchWriter`, `SettingsSource`, `BatchFolder` | Domínio |
| `adapters` | Implementações das portas (Pillow, pypdfium2, SQLite, zip e pasta, pastas locais e de rede, configuração em TOML) | Portas e a ferramenta que embrulham |
| `entrypoints` | API HTTP (FastAPI) e linha de comando `qa` | Aplicação e contrato |

A dependência sempre aponta para dentro; `engine/tests/test_architecture.py` cobra isso.
Diagramas: [contêineres](c4.md#contêineres) e [componentes](c4.md#componentes-do-motor).

Estrutura do repositório:

```text
contracts/      fonte da verdade: OpenAPI 3.1 + JSON Schema 2020-12
conformance/    gabarito, tolerâncias e executor que qualquer implementação precisa passar
engine/         implementação de referência em Python
ui/             interface web (React + TypeScript + Vite), tipos gerados do contrato
profiles/       perfis de cliente
tools/          gerador da base sintética, medidor de acerto e ferramentas de documentação
deploy/         empacotamento
docs/           esta documentação
```

## 6. Execução

A análise sobe de nível: primeiro cada página, depois cada documento, depois o lote
([diagrama](c4.md#pipeline)).

1. Descobrir documentos e páginas na pasta ([layout do lote](../especificacoes/batch-layout.md)).
2. Por página, em paralelo: decodificar, reduzir a 150 dpi, calcular a máscara de tinta e
   as medidas de cada regra ligada.
3. Calcular a linha de base do lote (mediana e desvio robusto de cada medida) e avaliar
   cada página contra ela.
4. Comparar páginas entre si (duplicatas).
5. Por documento: resolver a numeração de folhas e apontar falta, fora de ordem e dúvida
   ([sequência](../especificacoes/sequencing.md)).
6. Metadados, estado de cada documento e veredito do lote
   ([pontuação](../especificacoes/scoring.md)).
7. Revisão humana. Toda correção aceita gera uma cópia, reanalisada antes de ir para o
   lote corrigido ([correções](../especificacoes/corrections.md)).

## 7. Implantação

Uma imagem Docker (`deploy/Dockerfile`) com o motor, a interface compilada servida na
mesma origem e um lote de demonstração (ADR-0010).
Passo a passo em [Publicar a demonstração](../guias/publicar-demonstracao.md).

## 8. Conceitos transversais

- **Identificadores determinísticos**: a mesma entrada gera os mesmos identificadores e
  o mesmo relatório em qualquer máquina.
- **Auditoria**: cada decisão tem revisor, horário e, quando vem do "Corrigir tudo", o
  identificador da operação (ADR-0009).
- **Persistência**: SQLite com migrações em SQL puro (ADR-0005).
- **Erros da API**: RFC 9457 (`application/problem+json`).
- **Privacidade**: [dados guardados e por quanto tempo](../seguranca-e-privacidade/index.md).

## 9. Decisões

Uma página por decisão, no formato MADR, em `docs/adr/`.

## 10. Qualidade

Metas, como são medidas e os resultados atuais: [Testes](../testes/index.md).

## 11. Riscos e dívidas

| Risco | Mitigação |
| --- | --- |
| Resultados da base sintética são otimistas | Rodar em paralelo com a conferência humana num lote real já conferido antes de confiar nos números |
| Página faltando sem numeração nem contagem declarada é inverificável | Estado "completude não verificável"; pedir a contagem na preparação do lote |
| Falsa sensação de segurança | Amostragem obrigatória dos documentos verdes |
| Numeração lida errada | A sequência é resolvida no documento inteiro; dúvida vira revisão, nunca "página faltando" |
| Licença incompatível com produto fechado | ADR-0004 e revisão jurídica antes de distribuir |
