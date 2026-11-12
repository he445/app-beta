# Folha inserida depois

Quando a folha faltante aparece, o conferente escaneia só aquela folha e a solta na
tela de Sequência, no ponto onde ela deve entrar (ou na área "Adicionar folha", sem
escolher posição). Rota: `POST /batches/{id}/documents/{doc}/pages`.

## O que o motor faz

1. Confere o arquivo: TIFF, PNG, JPEG ou PDF, **uma folha por arquivo**; senão 422.
   Só depois da análise da caixa (409 antes).
2. Guarda a folha na **área de complementos** da pasta de trabalho do lote
   (`complementos/`), nunca na pasta original. O `source_file` da página começa com
   `:complemento:/` (o `:` não existe em nome de arquivo no Windows, então nunca colide
   com um arquivo do lote).
3. Analisa a folha como as outras: regras de página com a **linha de base gravada na
   análise do lote** e com os ajustes da estação padrão; leitura do número (com os
   modelos), recorte da região; folha com número nunca é branca.
4. Posição: a enviada (1 = antes da primeira) ou, sem ela, a **sugerida pelo número
   lido**: depois da maior folha do processo menor que ele; sem número lido, o fim.
   Com ordem manual, a folha entra na ordem manual; senão, na ordem do processo.
5. A sequência do processo é resolvida de novo com as marcas da folha nova (a lacuna
   fecha quando o número bate), e a numeração digitada e a ordem manual continuam
   valendo.
6. Se a caixa estava concluída, sai uma **versão nova do relatório por caixa**. O lote
   corrigido seguinte leva a folha na posição dela, renumerada com as outras.

A resposta traz a posição usada, a sugerida e o número lido, para a tela avisar quando
a folha entrou fora do lugar que o número indicava.

## Desfazer e auditoria

`DELETE /batches/{id}/documents/{doc}/pages/{page}` tira a folha (só folhas inseridas;
409 para uma página do lote original), apaga o arquivo da área de complementos e
resolve a sequência de novo. A tabela de complementos guarda quem inseriu, quando e
em que posição, e quem removeu.
