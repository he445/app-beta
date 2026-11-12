# 0020: Metadados do Decreto no lote corrigido, em XMP e num arquivo por processo

Status: aceito · Data: 2026-11-12 · Decisores: Everton Ferreira

## Contexto

O motor já calcula os metadados do Decreto 10.278/2020 e os técnicos, com a origem de
cada valor, mas o lote corrigido gravava no TIFF só fabricante, modelo, data e operador,
e trocava a tag Software. O cliente pode exigir os campos do Decreto embutidos no
arquivo, num arquivo de metadados por processo ou nos dois; isso ainda não foi
confirmado.

## Opções consideradas

1. Só tags embutidas (XMP no TIFF): o arquivo se explica sozinho, mas a origem de cada
   valor e a confirmação do revisor não cabem bem no XMP.
2. Só arquivo de metadados por processo: simples de ler e validar, mas o TIFF separado
   da pasta perde os metadados.
3. Os dois, escolhidos por perfil, com padrão nos dois.

## Decisão

Opção 3 ([especificação](../especificacoes/metadata.md#no-lote-corrigido)).

- Porta `MetadataReader` ganha `preserved(path, página)`: as tags do diretório principal
  do original (menos as estruturais), os valores da sub-IFD EXIF e o XMP original.
- Porta `CorrectedBatchWriter`: `add_page` recebe as tags preservadas e o XMP;
  `add_text` devolve o SHA-256, para o `hashes.sha256` listar todo arquivo entregue.
- Texto de tag TIFF é gravado com os mesmos bytes do original (o Pillow lê em latin-1);
  a parte que o programa escreve na tag Software vai em ASCII.
- Perfil: `delivery_metadata.embed_xmp` e `delivery_metadata.document_file`.

## Consequências

- Quando a coordenação confirmar o formato, basta ajustar o perfil do cliente.
- A sub-IFD EXIF não é regravada no TIFF (a biblioteca não grava a sub-IFD com Deflate):
  seus valores vão no XMP e no arquivo de metadados.
- XMP que o original já tinha é mantido como veio; nesse caso os campos do Decreto ficam
  só no arquivo do processo.
