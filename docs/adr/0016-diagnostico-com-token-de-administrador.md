# 0016: Diagnóstico de erros com token de administrador

Status: aceito · Data: 2026-11-11 · Decisores: Everton Ferreira

## Contexto

No beta, quem desenvolve não está ao lado da estação quando algo quebra. É preciso ver
os erros de todas as máquinas, agrupados, sem expor documento de cliente e sem abrir a
área para qualquer usuário da estação.

## Opções consideradas

1. Só o log em arquivo, recolhido à mão.
2. Serviço externo de monitoramento de erros. Descartado: dado sairia da máquina.
3. Registro local, agrupado por assinatura, numa tela protegida por token de
   administrador, com cópia opcional numa pasta compartilhada da rede.

## Decisão

Opção 3.

- **O que é capturado:** exceções das rotas (tratador global), falhas nos trabalhos de
  fundo (análise e correção em lote, incluindo erro de processo de análise), queda na
  abertura (o arquivo de queda é registrado na abertura seguinte) e erros da interface
  (error boundary do React, `window.onerror` e promessas rejeitadas sem tratamento, por
  `POST /diagnostics/client-errors`).
- **O que cada registro guarda:** data e hora, versão, computador, versão do sistema,
  usuário do Windows, gravidade, tipo, pilha, tela ou rota, lote e página. **Nunca** imagem
  nem texto de documento; caminhos absolutos são mascarados (`<caminho>`), inclusive com
  espaço no nome da pasta.
- **Agrupamento:** assinatura = tipo + local no código + mensagem sem números e
  identificadores. Um grupo resolvido volta a ficar aberto se o erro ocorrer de novo.
- **Onde fica:** banco local e, com `diagnostics_dir`, também um `<computador>.jsonl` na
  pasta compartilhada; a tela junta os de todas as máquinas.
- **Token de administrador:** `qa admin token` gera o token, mostra uma vez e grava só o
  hash (scrypt, biblioteca padrão) no arquivo da **máquina**; o arquivo do usuário e os
  argumentos não podem definir esse hash. As rotas `/admin/diagnostics/*` exigem
  `X-Admin-Token`; cinco tentativas erradas bloqueiam por um minuto (429). Sem hash, a
  área fica desligada (404). O token nunca aparece em log e, na interface, fica só na
  memória da aba.
- **Exportar pacote:** zip com registros, grupos, versão e configuração sem segredos.

## Consequências

- Migração `0004_diagnostics.sql`; contrato 0.9.0.
- O token de administrador também protegerá os ajustes de digitalizadora e o histórico
  de configuração.
