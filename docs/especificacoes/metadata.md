# Metadados

Versão: 1.0.0

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

## Saída

- `metadata/<documento>.json` por documento;
- `metadata.csv` por lote (uma linha por documento);
- XMP dentro do PDF com pikepdf: fase seguinte.
