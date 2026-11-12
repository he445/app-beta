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
| 9 | Fechar o programa no meio da caixa solta a trava na hora? | Não: a caixa continua com quem fechou por dez minutos (sem renovação, vira abandonada e pode ser assumida, com registro); ao abrir de novo, a mesma pessoa a retoma | Coordenação |
| 10 | Quem assume uma caixa abandonada começa do zero, sem as decisões da outra máquina? | Sim: cada máquina tem seu banco; a máquina que perdeu a caixa mostra o aviso e guarda o que já decidiu. Juntar os bancos fica para o servidor interno | Coordenação |
| 11 | Em que formato o cliente quer os metadados do Decreto no lote entregue: tags embutidas no arquivo, arquivo de metadados por processo ou os dois? | Os dois (`delivery_metadata` no perfil, com XMP e `metadados/<processo>.json`); as tags técnicas do original e `hashes.sha256` vão sempre | Coordenação, com o cliente |
| 12 | Ao voltar para a versão anterior, o que foi decidido na versão nova depois da atualização deve ser levado junto? | Não automaticamente: o banco da versão nova fica guardado ao lado e pode ser restaurado ao reinstalar a versão nova; a versão anterior volta ao banco de antes da atualização | Desenvolvimento, com a coordenação |
