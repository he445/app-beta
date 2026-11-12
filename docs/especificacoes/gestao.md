# Gestão

Junta os [relatórios por caixa](relatorio-por-caixa.md) de todas as máquinas, sem
servidor: cada caixa concluída grava o JSON na pasta compartilhada (`reports_dir`) e a
tela de Gestão lê essa pasta de qualquer computador. Sem `reports_dir`, a tela mostra só
as caixas deste computador e avisa.

## O que a tela mostra

- **Por conferente:** quantas caixas concluiu e quantas páginas; em cada caixa, o lote, a
  máquina, o estado (sem pendência, com pendência, pendência resolvida), os processos e,
  em cada processo, páginas, faltando e ilegíveis. O relatório abre em PDF.
- **Totais do período:** caixas concluídas, caixas com pendência, processos e páginas.
- **Versão do programa em cada máquina:** a do relatório mais recente de cada máquina,
  para achar estação esquecida numa versão antiga.

Fora por decisão: tempo gasto por caixa e ranking entre conferentes. Mudariam a
ferramenta de apoio para instrumento de cobrança individual; se a coordenação quiser,
entra como decisão registrada em ADR.

## Regras

- Uma caixa é identificada pelo lote e pelo número da caixa. Ela entra no período em
  que foi **concluída** (a primeira versão do relatório); o estado mostrado é o da
  versão mais nova até o fim do período.
- Períodos: dia, semana (segunda a domingo) ou mês, em hora local, como intervalo
  `[início, fim)` (`GET /management?since=...&until=...`).
- Arquivo da pasta compartilhada ilegível, incompleto (cópia em andamento) ou fora do
  contrato é pulado e contado; uma máquina com problema não derruba a tela.
- Abrir o relatório (`GET /management/report.pdf?ref=...`) só lê arquivos dentro de
  `reports_dir`.
