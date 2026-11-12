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
- **Versão do programa em cada máquina:** a da abertura mais recente do programa (cada
  máquina grava `maquinas/<computador>.json` na pasta compartilhada ao abrir e a cada
  hora, com versão e horário) ou, sem esse registro, a do último relatório. A máquina
  numa versão anterior à mais nova em uso (comparação SemVer) aparece como
  **desatualizada**, mesmo que ainda não tenha concluído caixa nenhuma. Sem
  `reports_dir`, só este computador.

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
