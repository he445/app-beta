# Questões em aberto

Dúvidas que apareceram durante a implementação. Em cada uma foi escolhida a opção
conservadora (a que não altera o original e manda para revisão humana) e a escolha ficou
registrada aqui até alguém decidir.

| # | Questão | Escolha atual | Quem decide |
| --- | --- | --- | --- |
| 1 | Uma chave travada pelo arquivo da máquina pode ser sobrescrita por variável `QA_*` ou argumento, para suporte e testes? | Não: travada vale para todas as camadas seguintes (ADR-0012) | TI |
| 2 | Arquivo bloqueado por outro programa conta como "crítico" no estado do documento? | Sim: a página não foi verificada. A correção sugerida é abrir o lote de novo, não redigitalizar | Coordenação |
| 3 | Número sozinho na página com um traço no meio (um 4 ou 7 que parece riscado) conta como riscado? | Não, salvo nota de riscado de 0,99: a sequência do documento acusa a divergência e o revisor decide (ADR-0015) | Coordenação |
