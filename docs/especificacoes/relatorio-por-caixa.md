# Relatório por caixa

Substitui a folha de papel em que se anotam as pendências. A hierarquia é **caixa →
processo → páginas**: a caixa é a primeira pasta do lote e o processo é o documento
([layout do lote](batch-layout.md)). Lote sem pastas é uma caixa só, com o nome do lote.

## Quando sai

Quando a caixa está **concluída**: toda sinalização médio ou acima das páginas e dos
documentos dela tem decisão (mandar para retrabalho também é decisão). Sinalização
baixa (`blank_page` "quase branca", `completeness_unverifiable`) é tratada em massa,
como na contagem de páginas que exigem revisão, e não segura a conclusão. Salvar o lote corrigido gera o
relatório de cada caixa concluída; `POST /batches/{id}/box-reports` faz o mesmo sob
pedido. Sai uma **versão nova** só quando as pendências mudaram desde a última (a
folha faltante apareceu, o retrabalho voltou); as anteriores ficam guardadas no banco e
nas pastas.

## Conteúdo

- **Cabeçalho:** caixa, conferente (o usuário do Windows no programa desktop), data e
  hora da conclusão, versão do relatório, estado, máquina e versão do programa.
- **Um item por processo** (o número é a última pasta do documento), com uma destas saídas:
  - **Páginas faltando:** sinalizações `missing_page` decididas como retrabalho ou
    defeito de origem; quantidade e quais folhas ("3 — fls. 13, 14 e 15").
  - **Páginas ilegíveis:** páginas com arquivo corrompido (`corrupted_file`) decidido
    como retrabalho ou defeito de origem: o arquivo não abre ou não se lê. Cada página
    conta uma vez; aparece o número da folha quando foi lido ou digitado, senão a
    posição no processo e o nome do arquivo.
  - **Defeitos de imagem, por tipo** ([ADR-0030](../adr/0030-defeitos-de-imagem-tipificados-no-relatorio-da-caixa.md)):
    a página se lê, mas tem o defeito confirmado como retrabalho ou defeito de origem.
    Sai uma linha por tipo: "Páginas desfocadas" (`blur`), "Páginas com exposição ruim
    (clara ou escura demais)" (`exposure`) e "Páginas com resolução abaixo do exigido"
    (`low_resolution`), cada página uma vez por tipo, com folha ou posição. No JSON, em
    `processes[].defects` e `totals.defects`; relatórios anteriores não têm esses campos
    e contavam esses defeitos em "ilegíveis".
  - **Nenhuma pendência.**

Número de folha ilegível com a página boa (`numbering_review`) não entra. Aprovar
("falso positivo") também não.

**Estado:** `pending` com alguma pendência; `resolved` sem pendência quando a versão
anterior tinha; `clean` sem pendência desde a primeira.

## Saída

JSON (`contracts/schemas/box-report.schema.json`) e PDF (A4), gravados:

- na pasta de saída: `Relatórios por caixa/<lote>/<caixa>-v<versão>.json|pdf`;
- com `reports_dir` configurado, na pasta compartilhada:
  `<reports_dir>/<máquina>/<caixa>-<lote, 8 caracteres>-v<versão>.json|pdf`, lida pela
  tela de Gestão.

Cada arquivo é gravado num temporário e renomeado. Falha ao gravar na pasta
compartilhada (rede fora) não impede salvar: vira aviso no diagnóstico e o relatório
continua no banco e na pasta de saída.
