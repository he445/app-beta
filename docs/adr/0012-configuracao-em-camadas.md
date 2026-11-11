# 0012: Configuração em camadas, validada por esquema

Status: aceito · Data: 2026-11-11 · Decisores: Everton Ferreira

## Contexto

O motor em servidor lia tudo de variáveis `QA_*`. Numa estação de trabalho isso não
serve: quem usa não é desenvolvedor, a TI precisa poder fixar algumas escolhas (de quais
pastas se abre lote, por exemplo) e o suporte precisa conseguir sobrescrever um valor sem
editar arquivo. Também há dois assuntos diferentes misturados na palavra "configuração":
o que descreve a máquina (pastas, núcleos, memória) e o que descreve o padrão de
qualidade (regras e limites).

## Opções consideradas

1. Tudo em variável de ambiente. Simples no servidor; difícil para quem não é
   desenvolvedor e sem como travar um valor.
2. Configuração no banco de dados. Editável pela tela, mas não versionável, não legível
   sem o programa e presa a uma máquina.
3. Arquivos de texto em camadas, validados por esquema, com as variáveis de ambiente como
   uma das camadas.

## Decisão

Opção 3.

- **A máquina em TOML, a qualidade em perfil.** O que descreve o computador fica em
  `config.toml`; regras e limites continuam no perfil YAML, que já é validado contra
  `profile.schema.json`.
- **Cinco camadas**, da mais fraca para a mais forte: padrões embutidos, arquivo da
  máquina, arquivo do usuário, variáveis `QA_*` e argumentos. As variáveis são as que o
  motor em servidor já lia; ele usa só os padrões e as variáveis.
- **Contrato:** `contracts/schemas/settings.schema.json`. Cada camada é validada sozinha,
  para o erro dizer a chave, a origem e o valor esperado. Configuração inválida impede o
  programa de abrir.
- **Chaves travadas** no arquivo da máquina (`[locked] keys`). Uma chave travada não é
  mudada por **nenhuma** camada seguinte, inclusive variáveis e argumentos: se a variável
  pudesse sobrescrever, a trava não protegeria nada, porque quem define a variável é o
  mesmo usuário.
- **Porta `SettingsSource`**, com o adaptador `LayeredSettings`. As pastas do sistema vêm
  de `platformdirs` (adaptador `AppPaths`).
- Segredo não vai em arquivo pela tela: `api_token` só entra por variável ou argumento e
  nunca é devolvido pela API.

## Consequências

- `platformdirs` (MIT) entra nas dependências (ADR-0004).
- TOML é lido com a biblioteca padrão (`tomllib`); a gravação, só de chaves simples, é
  feita pelo próprio adaptador, sem dependência nova.
- A referência de configuração é gerada do esquema (`docs/referencia/configuracao.md`).
- Testes cobrem a precedência das cinco camadas, as chaves travadas e os erros com
  origem (`engine/tests/test_settings.py`).
