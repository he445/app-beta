# Metadados do Decreto no lote corrigido

O motor já resolve os metadados do Decreto 10.278/2020 e os técnicos
([metadados](metadata.md)). O lote corrigido os leva em dois lugares, até a coordenação
confirmar o formato que o cliente exige na entrega (questão em aberto 10).

## No TIFF de cada página

- **Tags descritivas do original preservadas:** fabricante (271), modelo (272), autor
  (315), data (306, que passa a ser a da correção; a original vai no XMP), nome do
  documento (269), descrição (270), nome da página (285), computador (316) e direitos
  (33432). Tags ASCII do TIFF não levam acento: o texto vai sem acentos nelas e completo
  no XMP.
- **Correção registrada:** `Software` (305) =
  `qa-digitalizacao <versão> (lote corrigido: <o que mudou>)`, por exemplo
  "endireitada 2,3°; girada 90°", ou "sem alteração da imagem"; `DateTime` (306) = a
  hora em que o lote corrigido foi gerado.
- **XMP (tag 700):** `xmp:CreatorTool`, `xmp:ModifyDate`, `qa:dataOriginal` (data do
  arquivo original), `qa:campos` (cada campo do Decreto com `qa:campo`, `qa:valor`,
  `qa:origem` e `qa:confirmado`) e `qa:correcoes` (o que mudou na página). Espaço de
  nomes `https://qa-digitalizacao.local/ns/decreto-10278/1.0/`.

## Por processo: `metadados.json`

Na pasta de cada processo do lote corrigido
(`contracts/schemas/process-metadata.schema.json`): cada campo com valor, origem (`source`
e o texto `source_label`: do arquivo, do perfil, calculado, informado pelo revisor...),
se o Decreto exige e se foi confirmado; e cada arquivo entregue com o **SHA-256**, o
arquivo de origem com o SHA-256 dele e o que mudou.

O `manifest.json` do lote corrigido continua com o SHA-256 de cada página (`target_sha256`).
