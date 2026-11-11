# Segurança e privacidade

## Dados que o sistema guarda

| O quê | Onde | Por quanto tempo |
| --- | --- | --- |
| Lote enviado pelo navegador | `QA_DATA_DIR/batches/<id>/input` | `QA_RETENTION_HOURS` (padrão 24 h); depois é apagado |
| Cópias corrigidas das páginas e log de correções | `QA_DATA_DIR/batches/<id>/corrected` | Junto com o lote |
| Relatório, sinalizações, decisões e histórico | `QA_DATA_DIR/qa.sqlite3` | Junto com o lote |
| Lote local (pasta lida no lugar) | Na pasta original | Nunca é copiado, alterado nem apagado; só o retrato e as cópias corrigidas ficam em `data_dir/batches/<id>` |
| Lote corrigido gravado em pasta | `output_dir` | Até alguém apagar |

O motor em nuvem só deve receber documentos sintéticos ou públicos
([princípio 1](../visao-geral/principios.md)); a tela de envio avisa isso. Documento de
cliente só é processado dentro da rede da empresa.

## Acesso

- Com `QA_API_TOKEN` definido, as rotas da API exigem `Authorization: Bearer <token>`.
  Sem ele, a API fica aberta: só para desenvolvimento local e para a demonstração com
  dados sintéticos (ADR-0010).
- `GET /health` e a interface servida na mesma origem são públicos e não expõem dado de
  lote.
- O CORS só aceita as origens listadas em `QA_CORS_ORIGINS`; servindo a interface na
  mesma origem, nenhuma origem é liberada.
- Envios são limitados por `QA_MAX_UPLOAD_MB`, e nomes de arquivo com `..` ou caminho
  absoluto são recusados.

## O original nunca é alterado

O motor só lê o lote. Correções são gravadas em cópias, e o lote corrigido é um arquivo
novo com manifesto e SHA-256 de cada página de origem e de destino
([correções](../especificacoes/corrections.md)).

## Dependências

Política e lista em [Licenças de terceiros](licencas.md).
