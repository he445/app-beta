# Questões em aberto

Dúvidas que apareceram durante a implementação. Em cada uma foi escolhida a opção
conservadora (a que não altera o original e manda para revisão humana) e a escolha ficou
registrada aqui até alguém decidir.

| # | Questão | Escolha atual | Quem decide |
| --- | --- | --- | --- |
| 1 | Uma chave travada pelo arquivo da máquina pode ser sobrescrita por variável `QA_*` ou argumento, para suporte e testes? | Não: travada vale para todas as camadas seguintes (ADR-0012) | TI |
| 2 | Arquivo bloqueado por outro programa conta como "crítico" no estado do documento? | Sim: a página não foi verificada. A correção sugerida é abrir o lote de novo, não redigitalizar | Coordenação |
| 3 | Número sozinho na página com um traço no meio (um 4 ou 7 que parece riscado) conta como riscado? | Não, salvo nota de riscado de 0,99: a sequência do documento acusa a divergência e o revisor decide (ADR-0015) | Coordenação |
| 4 | Defeito que o garantidor acha e o programa não sinalizou (fora giro e numeração) entra na cobertura? | Não há como registrar ainda: a cobertura do `beta report` é estimada só com giros e numerações que o garantidor corrigiu sozinho | Coordenação |
| 5 | O recorte guardado para o ajuste fino é a região inteira do canto ou só o número digitado? | A região inteira (com tudo que estava escrito); o rótulo é o número digitado | Desenvolvimento, com os primeiros exemplos do beta |
| 6 | A coleta do beta (recortes e miniaturas de páginas de clientes) tem o aval de LGPD? | Ligada no perfil do piloto com retenção de 180 dias, só nesta máquina; desligar no perfil se o aval não vier antes do piloto | Encarregado de LGPD |
| 7 | A caixa é mesmo a primeira pasta do lote e o processo a pasta do documento, na estrutura real da amostra? | Sim (como a ordem de retrabalho já identifica); lote sem pastas vira uma caixa com o nome do lote | Coordenação |
| 8 | "Página ilegível" no relatório por caixa é só a confirmada numa regra de legibilidade (desfoque, exposição, resolução, arquivo corrompido)? | Sim, decidida como retrabalho ou defeito de origem; número de folha ilegível com a página boa não entra | Coordenação |
| 9 | Duas caixas de clientes diferentes podem ter o mesmo nome de pasta (CX001)? A trava é pelo nome da caixa | Sim, pelo nome: na dúvida trava a mais (a segunda pessoa vê o aviso e quem está com a caixa) | Coordenação |
| 10 | Formato dos metadados do Decreto na entrega: tags embutidas no TIFF, arquivo por processo, ou os dois? | Os dois: XMP e tags no TIFF e `metadados.json` por processo, com a origem de cada valor e o SHA-256 de cada arquivo | Coordenação, com o que o cliente exige |
