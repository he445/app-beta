# Correções, correção em lote e lote corrigido

Versão: 1.0.0 · ADR-0009

## Versão corrigida de uma página

A versão corrigida de uma página é **o original com todas as correções de imagem
decididas como `correct`**, aplicadas numa ordem canônica que não depende da ordem das
decisões. O original nunca é alterado (princípio 2).

Ordem canônica (empate: identificador da sinalização):

| # | Ação | Por que nessa posição |
| --- | --- | --- |
| 1 | `autocrop` | as frações de recorte foram medidas no original |
| 2 | `rotate` | orientação medida no original |
| 3 | `mirror` | idem |
| 4 | `deskew` | o ângulo não muda com o recorte; girar depois não desloca as bordas já removidas |
| 5 | `despeckle` | filtros locais depois da geometria |
| 6 | `auto_levels` | idem |
| 7 | `to_grayscale` | último: os ajustes trabalham na cor original |

Cada versão gravada vira um evento no log só de inserção (`corrected/corrections.jsonl`)
com a cadeia (`chain`), o arquivo gerado, os SHA-256 de origem e destino, quem decidiu,
quando e a operação em lote, se houver. Uma versão já gravada para a mesma cadeia é
reaproveitada: desfazer volta ao mesmo arquivo, byte a byte.

**Correções proibidas** nunca são oferecidas: aumentar resolução por
interpolação, nitidez artificial, clarear página ilegível, preencher área cortada.

## "Corrigir tudo"

Escopo: um documento ou o lote inteiro. Considera só sinalizações **sem decisão**.

```text
para cada sinalização sem decisão no escopo:
    se correção.kind = automatic
       e ação ∈ {deskew, rotate, mirror, autocrop, despeckle, auto_levels, to_grayscale}
                 (alvo página) ∪ {remove_page} (alvo página) ∪ {reorder} (alvo documento)
       e regra ∉ {missing_page, duplicate_page} ∪ REDIGITALIZAR:
        decide correct (revisor, horário, operation_id)
    senão: fica pendente, com a categoria:
        missing_page   → regra missing_page: exige aprovação manual
        needs_rescan   → regra ∈ REDIGITALIZAR ou correção.kind = physical:
                         precisa redigitalizar; vai para a ordem de retrabalho
        manual         → o resto (duplicata nunca é removida automaticamente)
REDIGITALIZAR = {blur, low_resolution, corrupted_file, cropped_content, truncated_image}
```

Unidades de progresso, na ordem dos documentos e das páginas: uma por página com
correção (todas as correções de imagem da página numa única renderização) e uma por
documento com reordenação. O progresso gravado é `done` de `total` unidades. Falha numa
página não interrompe as outras: ela volta como `failed`.

Só uma operação por lote pode estar em andamento (`409` para a segunda).

### Desfazer em lote

Remove a decisão das sinalizações que **ainda** carregam o `operation_id` da operação
(uma decisão trocada depois, individualmente, não é tocada), recalcula a versão das
páginas afetadas e registra `undo` no histórico. O relatório volta exatamente ao estado
anterior à operação.

## Plano do lote corrigido

Por documento, com as decisões atuais:

1. **Ordem final:** `proposed_order` se a sinalização `out_of_order` foi decidida
   `correct`; senão, a ordem do arquivo.
2. **Removidas:** páginas com `remove_page` decidido `correct` (motivo: "em branco",
   "duplicada").
3. **Não exportadas:** páginas que não decodificam ("arquivo ilegível: precisa redigitalizar").
4. **Renumeração:** as exportadas recebem `0001.tif`, `0002.tif`... na ordem final.
5. **Movida:** a posição relativa entre as exportadas mudou por causa da reordenação
   ("movida da posição 7 para a 6"). Subir de posição só porque outra foi removida não
   é "movida".
6. **Precisa redigitalizar:** sinalizações pendentes de redigitalização da página; a
   página vai como está.
7. **Página faltando:** cada `missing_page`, com a decisão. **Salvar é recusado
   enquanto houver página faltando sem decisão** (retrabalho, defeito de origem ou
   aprovar mesmo assim).

Pasta de cada documento: a mesma do original (`caixa/documento`); documento vindo de
um arquivo multipágina vira uma pasta com o nome do arquivo sem extensão.

## Lote corrigido (.zip)

- TIFF com compressão **sem perda** (Deflate, tag 259 = 8), nunca JPEG (Decreto
  10.278/2020, Anexo I);
- DPI do original (PDF: 300 dpi, a resolução de rasterização);
- monocromático continua em 1 bit; tags de captura (fabricante, modelo, data, operador)
  copiadas do original, `Software` = `qa-digitalizacao <versão> (lote corrigido)`;
- `manifest.json` (`contracts/schemas/corrected-manifest.schema.json`) e `manifest.csv`:
  arquivo e página de origem, arquivo de destino, posição antiga e nova, correções com
  quem decidiu e quando, SHA-256 de origem e destino, removidas e o motivo,
  redigitalizar, páginas faltando e a decisão;
- gerado em `<lote>/exports/lote-corrigido.zip` (arquivo parcial renomeado no fim).
