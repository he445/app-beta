# Layout do lote

Versão: 1.0.0

## Entrada

Uma pasta (ou um `.zip` extraído numa pasta) com arquivos `.tif`, `.tiff`, `.jpg`,
`.jpeg`, `.png` e `.pdf`. Arquivos e pastas ocultos (nome iniciado por `.`) são
ignorados. Nomes reservados na raiz:

| Arquivo | Conteúdo | Esquema |
| --- | --- | --- |
| `manifest.csv` | Contagem declarada: colunas `document,pages` | — |
| `numbering.json` | Marcas de numeração por página | `numbering-sidecar.schema.json` |
| `index.csv` | Índice exportado do software de captura (validação na fase seguinte) | — |

## Algoritmo

```text
arquivos ← todos os arquivos suportados, em ordem natural do caminho relativo
para cada arquivo:
    se for PDF ou tiver mais de uma página: documento próprio, nome = caminho sem extensão
    senão: entra no documento da sua pasta, nome = caminho relativo da pasta
           (imagens soltas na raiz: nome = nome do lote)
documentos ← ordenados em ordem natural do nome
```

Ordem natural: o texto é quebrado em trechos de dígitos e não dígitos; dígitos comparam
como inteiros, o resto em minúsculas. `p2` vem antes de `p10`.

A chave de página usada em `numbering.json` é `caminho/relativo#n`, com `n` a partir de 0.

## Identificadores

UUID v5 determinísticos (`engine/src/qa_engine/domain/ids.py`):

- lote: `uuid5(NS, "batch/" + sha256(concat(rel + "\0" + sha256(arquivo) + "\n")))`;
- documento: `uuid5(lote, "document/" + nome)`;
- página: `uuid5(lote, "page/" + rel + "#" + n)`;
- sinalização: `uuid5(lote, "finding/" + alvo + "/" + regra + "/" + ordinal)`.

`NS = 6f1c2b8e-4a77-5d0e-9c3a-2f3b9d1e7a10`.

## Falhas

Arquivo que não decodifica (0 byte, truncado, formato inválido) não interrompe o lote:
vira uma página com `loaded = false` e a regra [`corrupted_file`](detectors/corrupted_file.md).

## Estação de cada página

Cada arquivo é ligado à primeira estação do perfil cujos campos informados (`make`,
`model`, `serial` comparados sem diferença de maiúsculas com as tags do arquivo; `folder`
comparada com o caminho relativo) batem todos. Sem estação compatível, vale a estação de
reserva (`default_station` do computador ou a escolhida ao abrir o lote), se ela existir
no perfil. Todas as páginas de um arquivo têm a mesma estação.

Os parâmetros de cada regra numa página seguem a ordem: manifesto da regra, `detectors`
do perfil, `overrides` da estação. A linha de base de uma regra é calculada sobre todas
as páginas em que ela está ligada, e cada página é avaliada com os seus parâmetros.
