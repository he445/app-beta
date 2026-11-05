# low_resolution: Resolução abaixo do exigido

Versão: 1.0.0 · Severidade padrão: alto

## Objetivo

Conferir o DPI gravado no arquivo contra o mínimo do perfil (Anexo I do Decreto
10.278/2020: 300 dpi; 600 dpi para plantas e mapas).

## Entrada

DPI horizontal gravado: tag de resolução de TIFF/JPEG/PNG; em PDF, o DPI efetivo da maior
imagem embutida na página.

## Algoritmo

```text
se DPI ausente: sinaliza com measure = 0, confiança 0,3, correção escalate/human_review
senão se DPI < min_dpi − 0,5: sinaliza com confiança 1, correção physical/rescan
```

## Parâmetros

| Nome | Tipo | Padrão |
| --- | --- | --- |
| `min_dpi` | número | 300 (ou `resolution.min_dpi` do perfil) |

## Saída

`measure` = DPI; `threshold` = `min_dpi`; `params.dpi` = resolução a configurar.

## Falhas conhecidas e casos de borda

- Aumentar resolução por interpolação é correção proibida: a única proposta é redigitalizar.
- DPI gravado errado (arquivo reamostrado sem atualizar a tag) não é detectado.

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0003/0005.tif` (200 dpi).

## Histórico de versões

- 1.0.0: versão inicial.
