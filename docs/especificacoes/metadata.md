# Metadados

Versão: 1.1.0

Cada metadado é um `MetadataField` (`contracts/schemas/metadata-field.schema.json`) com
valor, **fonte** e **confiança**. Nenhuma sugestão vale sem confirmação do revisor
(`confirmed = false` até lá).

## Decreto 10.278/2020, Anexo II, item a (por documento)

Lidos do primeiro arquivo do documento.

| Campo | Fonte | Confiança |
| --- | --- | --- |
| `scan_date` | tag de data (TIFF DateTime, EXIF DateTimeOriginal, PDF CreationDate) → `file_tag`; na falta, data de modificação → `file_mtime` | 0,95 / 0,3 |
| `scan_location` | primeira estação do perfil cujos campos `make`, `model`, `serial` e `folder` informados coincidem (sem diferenciar maiúsculas; `folder` por prefixo do caminho) → `profile` | 0,9 / 0 |
| `responsible` | `organization` do perfil + operador da tag Artist, se houver | 0,8 / 0,6 |
| `identifier` | `identifier_pattern` com `{batch}`, `{document}` (barras viram hífen) e `{seq}` (4 dígitos) → `generated` | 1 |
| `hash_sha256` | SHA-256 do arquivo (ou mapa arquivo → hash) → `computed` | 1 |
| `title`, `document_type`, `author`, `subject` | OCR (porta `OcrEngine`, fase seguinte) → hoje `unavailable` | 0 |

Datas EXIF (`AAAA:MM:DD hh:mm:ss`) e PDF (`D:AAAAMMDDhhmmss`) sem fuso são tratadas como UTC.

## Técnicos (Anexo I)

`make`, `model`, `software`, `dpi`, `color_mode`, `bit_depth`, `compression`, `format`,
`page_count`, `size_bytes` e, com DPI, `width_mm` e `height_mm` (`px / dpi × 25,4`,
1 casa).

Arquivos com compressão com perda (`jpeg`, inclusive JPEG dentro de TIFF) entram em
`summary.lossy_files`: o Anexo I exige compressão sem perda.

## Saída (exportações do relatório)

- `metadata/<documento>.json` por documento;
- `metadata.csv` por lote (uma linha por documento);
- XMP dentro do PDF com pikepdf: fase seguinte.

## No lote corrigido

Decisão em [ADR-0020](../adr/0020-metadados-do-decreto-no-lote-corrigido.md). O formato
final que o cliente exige ainda vai ser confirmado com a coordenação; por isso o perfil
escolhe onde vão os campos do Decreto (`delivery_metadata`), e o padrão é nos dois
lugares.

**Sempre, em cada TIFF entregue:**

- **Tags técnicas do original preservadas:** todas as do diretório principal do TIFF
  (fabricante, modelo, data, operador, computador, descrição, direitos autorais e as
  demais), byte a byte, menos as que descrevem a imagem codificada (tamanho, compressão,
  faixas, orientação, cores), que o gravador refaz. Do JPEG e do PNG vêm as tags de
  captura do EXIF. Os valores da sub-IFD EXIF (data original, data de digitalização,
  número de série, identificador único) vão no XMP: a biblioteca não grava a sub-IFD
  junto com a compressão Deflate.
- **Software:** a tag do original seguida de
  `qa-digitalizacao <versão> (corrigida: <correções>)` ou `(sem correcao de imagem)`, em
  ASCII (a especificação TIFF pede texto de 7 bits). As correções incluem o reposicionamento.
- **Data (DateTime):** a da digitalização na página sem correção de imagem; a da
  correção na página corrigida, e a da digitalização vai para `exif:DateTimeOriginal` no
  XMP.
- Página de PDF: o PDF não tem essas tags; só os campos do Decreto e a trilha.

**Campos do Decreto** (`delivery_metadata.embed_xmp`, padrão sim): XMP (tag 700) com
Dublin Core onde há equivalente (`dc:identifier`, `dc:title`, `dc:creator` = autor,
`dc:subject`, `dc:type` = tipo de documento), `xmp:CreateDate` = data da digitalização,
`xmp:ModifyDate` na página corrigida, e no espaço de nomes `urn:qa-digitalizacao:metadados:1`
o local, o responsável, o arquivo e o SHA-256 de origem e as correções. Original que já
tinha XMP mantém o seu, sem mudança.

**Arquivo por processo** (`delivery_metadata.document_file`, padrão sim):
`metadados/<pasta do processo>.json` (`contracts/schemas/delivery-metadata.schema.json`)
com cada campo do Decreto e técnico: valor, origem (`source` e `source_label`: do
arquivo, data do arquivo, do perfil, gerado pelo programa, calculado, lido por OCR,
informado pelo revisor, não disponível), confiança e se o revisor confirmou; e cada
arquivo entregue com o SHA-256, a origem, as correções, as tags preservadas e se leva
XMP.

**Sempre, no lote:** `hashes.sha256` com o SHA-256 de cada arquivo entregue (páginas,
metadados, manifestos e relatórios), no formato do `sha256sum`
(`sha256sum -c hashes.sha256` confere o lote).
