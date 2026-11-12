# Backup do banco

Decisões, auditoria, numeração digitada, histórico de configuração e de travas vivem no
SQLite de cada máquina (`data_dir/qa.sqlite3`). Se o computador pifar no meio do beta,
eles sumiriam. O programa desktop copia o banco para a pasta compartilhada da rede.

## Quando

- **Uma vez por dia:** a cada minuto o programa confere a cópia mais nova; com mais de
  24 horas (ou nenhuma), faz uma. Logo ao abrir também confere.
- **Ao fechar** o programa, sempre.

## Como

- A cópia usa a **API de backup do SQLite**: é consistente mesmo com o programa
  gravando no mesmo instante.
- Vai para `<backup_dir>/<máquina>/<usuário>/qa-AAAAMMDD-HHMMSS.sqlite3` (horário UTC),
  gravada num arquivo `.part` e renomeada no fim: uma cópia interrompida nunca parece
  pronta.
- Ficam as **14 cópias mais recentes** de cada máquina e usuário; as mais antigas são
  apagadas na cópia seguinte.
- Sem `backup_dir`, as cópias ficam em `data_dir/backups/<máquina>/<usuário>` (protegem
  contra banco corrompido, não contra o computador pifar).
- Com `backup_dir` fora do ar, a cópia do dia vai para `data_dir/backups`, a falha vira
  aviso no [Diagnóstico](../operacao/diagnostico.md) e a pasta compartilhada é tentada
  de novo depois de uma hora (não a cada minuto).

O que não entra: miniaturas, cópias corrigidas das páginas e recortes, que são cache
com prazo ([retenção](../seguranca-e-privacidade/index.md)) e se refazem a partir do
lote original.

## Restaurar

Com o programa **fechado** (`QA-suporte.exe` no pacote, `qa` em desenvolvimento):

```text
QA-suporte.exe backup list            # cópias desta máquina e deste usuário
QA-suporte.exe backup list --all      # de todas as máquinas (máquina nova)
QA-suporte.exe backup restore --latest
QA-suporte.exe backup restore "\\servidor\qa\backups\MAQ-1\maria\qa-20261112-180000.sqlite3"
QA-suporte.exe backup now             # uma cópia agora
```

`restore`:

1. Recusa se o programa estiver aberto nesta conta (trava de instância em `data_dir`).
2. Confere a cópia: `PRAGMA integrity_check` e as migrações gravadas nela. Cópia
   corrompida, ou de uma versão **mais nova** do programa, é recusada sem mexer em nada.
3. Se já existe banco, guarda-o ao lado como
   `qa.sqlite3.antes-da-restauracao-AAAAMMDD-HHMMSS`.
4. Copia a cópia para `data_dir/qa.sqlite3` (num arquivo temporário renomeado no fim) e
   aplica as migrações que faltam, se a cópia for de uma versão anterior.

Numa **máquina nova**, instale o programa, rode `backup list --all`, escolha a cópia da
máquina antiga e restaure. Ao abrir, decisões e auditoria estão de volta; as caixas que
a máquina antiga tinha travado são retomadas pela renovação, desde que ninguém as tenha
assumido ([trava por caixa](trava-por-caixa.md)).

## Troca de versão

- Ao abrir, antes de qualquer migração, o motor compara as migrações gravadas no banco
  com as que conhece:
  - **faltam migrações** (versão nova): copia o banco para
    `data_dir/atualizacoes/qa-antes-da-<versão nova>-de-<versão anterior>-<data>.sqlite3`
    pela API de backup e só então migra; ficam as cinco cópias mais recentes;
  - **o banco tem migração que esta versão não conhece** (alguém voltou para a versão
    anterior): não abre e não mexe em nada. O programa desktop mostra a tela de volta de
    versão, que restaura a cópia de antes da atualização mais recente que esta versão
    consegue abrir; o banco atual fica ao lado.
- Cada versão que abre o banco fica registrada (`program_versions`, migração 0012), para
  a cópia dizer de qual versão veio.
- `qa backup restore --before-update` faz a mesma restauração pela linha de comando.

Guia passo a passo: [Atualizar e voltar de versão](../guias/atualizar-e-voltar-versao.md).

## Privacidade

As cópias têm o mesmo conteúdo do banco: decisões, nomes de conferentes e nomes de
arquivos, nenhuma imagem de página. Seguem as regras de retenção e LGPD do banco local;
o acesso à pasta compartilhada é definido pela TI.
