# Correções, correção em lote e lote corrigido

Versão: 1.1.0 · ADR-0009, ADR-0024

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
reaproveitada: desfazer volta ao mesmo arquivo, byte a byte. A cadeia é comparada por
sinalização, ação e parâmetros (uma rotação trocada de 90° para 270° grava outra versão).

**Correções proibidas** nunca são oferecidas: aumentar resolução por
interpolação, nitidez artificial, clarear página ilegível, preencher área cortada.

## "Corrigir pasta" e "Corrigir tudo"

Escopo: um documento (**Corrigir pasta**) ou o lote inteiro (**Corrigir tudo**), e
opcionalmente só uma regra (`rule`). Considera só sinalizações **sem decisão**.

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

**Com a caixa em análise** (liberação por processo), a operação vale para os processos
já prontos: o documento pedido tem de estar pronto (`409` se ainda está em análise), e o
escopo de lote inteiro volta com `partial: true`. As decisões entram como as individuais
e a passada final as mantém (ADR-0024).

## "Decidir semelhantes" e "Aprovar tudo"

Pedido com `action` (`approve`, `reject` ou `source_defect`), no escopo de um documento ou
do lote. Com `rule`, vale só para aquela regra ("Decidir semelhantes"); sem `rule`, para
todas ("Aprovar tudo como defeito de origem", [ADR-0031](../adr/0031-aprovar-tudo-como-operacao-em-lote.md)).
`note` é a ressalva do revisor, gravada em cada decisão; `include_missing` deixa entrar
página faltando. `note` e `include_missing` sem `action`: 422.

```text
se página faltando pedida (rule = missing_page) sem include_missing: 422
para cada sinalização sem decisão do escopo (da regra, se dada):
    se é página faltando e não include_missing: pula
    decide action (revisor, horário, note, operation_id)
```

Uma unidade de progresso por documento; nenhuma imagem é regravada (só `correct` muda a
cadeia de correções da página). `correct` não é aceito como decisão em lote. O
resultado traz `applied_by_rule` e nada em `skipped`. Desfazer em lote vale do mesmo
jeito. Essas decisões não viram exemplo da coleta do beta.

### "Aprovar tudo (defeito de origem)", no painel

A interface pede uma operação do lote inteiro com `action = source_defect`, sem `rule` e
com a ressalva em `note`. Página faltando só entra (`include_missing`) depois de um alerta
próprio que lista cada pasta com as folhas que faltam; sem essa confirmação ela fica para
o cartão da Sequência. O andamento e o Desfazer em lote aparecem no painel.

### Desfazer em lote

Remove a decisão das sinalizações que **ainda** carregam o `operation_id` da operação
(uma decisão trocada depois, individualmente, não é tocada), recalcula a versão das
páginas afetadas e registra `undo` no histórico. O relatório volta exatamente ao estado
anterior à operação.

## Plano do lote corrigido

Por documento, com as decisões atuais:

1. **Ordem final:** `manual_order` quando o revisor reordenou na tela de Sequência
   (cada página movida registra "movida da posição X para a Y pelo revisor", com revisor
   e horário); senão `proposed_order` se a sinalização `out_of_order` foi decidida
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

## Lote corrigido (.zip ou pasta)

- TIFF com compressão **sem perda** (Deflate, tag 259 = 8), nunca JPEG (Decreto
  10.278/2020, Anexo I);
- DPI do original (PDF: 300 dpi, a resolução de rasterização);
- monocromático continua em 1 bit; as tags técnicas do original são preservadas, a tag
  `Software` registra o que o programa fez com a página e os campos do Decreto vão num
  XMP e em `metadados/<processo>.json`
  ([metadados no lote corrigido](metadata.md#no-lote-corrigido));
- `hashes.sha256`: SHA-256 de cada arquivo entregue, no formato do `sha256sum`;
- `manifest.json` (`contracts/schemas/corrected-manifest.schema.json`) e `manifest.csv`:
  arquivo e página de origem, arquivo de destino, posição antiga e nova, correções com
  quem decidiu e quando, SHA-256 de origem e destino, removidas e o motivo,
  redigitalizar, páginas faltando e a decisão;
- `configuracao.json`: o resumo de configuração do lote (perfil, computador e histórico
  recente de mudanças de configuração).
- `report.json` (relatório com as decisões vigentes), `findings.csv` e `decisions.csv`
  (registro de todas as decisões, inclusive as desfeitas, com quem e quando);
- destino `zip`: `<lote>/exports/lote-corrigido.zip` (arquivo parcial renomeado no fim);
- destino `folder`: `output_dir/<lote>-corrigido-<AAAAMMDD-HHMMSS>`, com a mesma
  estrutura. A gravação é feita na pasta oculta `.<nome>.part` e só renomeada para o nome
  final quando termina; uma falha no meio apaga a pasta parcial. Se o nome já existir,
  ganha o sufixo `-2`, `-3`...

**Lote local:** antes de gravar, a pasta original é comparada com o retrato tirado
antes da análise (tamanho, data e SHA-256 de cada arquivo; com tamanho e data iguais, o
arquivo é considerado igual). Qualquer arquivo novo, removido ou alterado recusa a
gravação com a lista do que mudou ([lote local](lote-local.md)).
