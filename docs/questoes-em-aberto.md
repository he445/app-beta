# Questões em aberto

Dúvidas que apareceram durante a implementação. Em cada uma foi escolhida a opção
conservadora (a que não altera o original e manda para revisão humana) e a escolha ficou
registrada aqui até alguém decidir.

| # | Questão | Escolha atual | Quem decide |
| --- | --- | --- | --- |
| 1 | Uma chave travada pelo arquivo da máquina pode ser sobrescrita por variável `QA_*` ou argumento, para suporte e testes? | Não: travada vale para todas as camadas seguintes (ADR-0012) | TI |
