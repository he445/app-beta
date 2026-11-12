# Backup do banco

As decisões, a numeração digitada, a auditoria e o histórico ficam no banco local de
cada computador. Se o computador pifar no meio do beta, eles iriam junto; por isso o
programa copia o banco sozinho:

- **quando abre** (se a última cópia tem mais de um dia), **uma vez por dia** enquanto
  fica aberto e **ao fechar**;
- para a pasta compartilhada `backup_dir` (configurada pela TI), numa pasta com o nome
  da máquina; sem ela, para `backups` na pasta de dados deste computador (protege
  contra banco corrompido, não contra máquina perdida);
- ficam as **14 cópias mais novas** de cada máquina. As cópias seguem as mesmas regras
  de retenção e LGPD dos dados do programa.

A cópia é consistente mesmo com o programa aberto (API de backup do SQLite). Falha ao
gravar (rede fora) vira aviso no Diagnóstico e não atrapalha o trabalho.

## Restaurar

Numa máquina nova ou depois de uma falha, **com o programa fechado**:

```text
QA-suporte.exe backup list
QA-suporte.exe backup restore qa-20261201-180000.sqlite3
```

`restore` aceita o nome de uma cópia da lista ou o caminho de um arquivo (por exemplo,
da pasta de outra máquina em `backup_dir`). A cópia é conferida antes (íntegra e do
programa); o banco que estava no lugar fica guardado ao lado, com
`antes-da-restauracao` no nome. `QA-suporte.exe backup now` faz uma cópia na hora.

Os lotes voltam com as decisões e a auditoria. As pastas originais dos lotes continuam
onde estavam; as cópias corrigidas e os recortes da pasta de trabalho não vão no banco.
