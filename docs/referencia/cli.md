<!-- Gerado por tools/docs/gen_reference.py. Não edite: mude a fonte e gere de novo. -->

# Referência da linha de comando

O comando `qa` usa os mesmos casos de uso da API, sem interface. Rode com
`uv run --project engine qa <comando>`.

## `qa`

```text
usage: qa [-h] [--version]
          {analyze,rules,validate-profile,admin,feedback,beta,backup,validate-report} ...

QA automático de digitalização

positional arguments:
  {analyze,rules,validate-profile,admin,feedback,beta,backup,validate-report}
    analyze             analisar um lote local
    rules               listar as regras registradas
    validate-profile    validar um perfil contra o contrato
    admin               administração desta máquina
    feedback            coleta do beta (exemplos confirmados)
    beta                acompanhamento do piloto
    backup              cópias do banco local (decisões e auditoria)
    validate-report     validar um report.json contra o contrato

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## `qa analyze`

```text
usage: qa analyze [-h] [--profile PROFILE] --out OUT [--workers WORKERS] [--models MODELS]
                  [--quiet]
                  batch

positional arguments:
  batch              pasta do lote

options:
  -h, --help         show this help message and exit
  --profile PROFILE  perfil YAML do cliente
  --out OUT          pasta de saída
  --workers WORKERS  processos (1 = em série)
  --models MODELS    pasta dos modelos (orientação da página)
  --quiet
```

## `qa rules`

```text
usage: qa rules [-h]

options:
  -h, --help  show this help message and exit
```

## `qa validate-profile`

```text
usage: qa validate-profile [-h] profile

positional arguments:
  profile

options:
  -h, --help  show this help message and exit
```

## `qa admin`

```text
usage: qa admin [-h] {token} ...

positional arguments:
  {token}
    token     gerar o token de administrador (diagnóstico)

options:
  -h, --help  show this help message and exit
```

## `qa admin token`

```text
usage: qa admin token [-h] [--config CONFIG]

options:
  -h, --help       show this help message and exit
  --config CONFIG  arquivo da máquina (padrão: o do sistema)
```

## `qa feedback`

```text
usage: qa feedback [-h] {export} ...

positional arguments:
  {export}
    export    gerar o pacote para o ajuste fino

options:
  -h, --help  show this help message and exit
```

## `qa feedback export`

```text
usage: qa feedback export [-h] --out OUT [--kind {numbering,orientation}] [--since SINCE]
                          [--until UNTIL] [--data-dir DATA_DIR]

options:
  -h, --help            show this help message and exit
  --out OUT             arquivo .zip de saída
  --kind {numbering,orientation}
                        só um tipo
  --since SINCE         a partir de (ISO 8601, ex.: 2026-12-01)
  --until UNTIL         antes de (ISO 8601)
  --data-dir DATA_DIR   pasta de dados (padrão: a desta conta)
```

## `qa beta`

```text
usage: qa beta [-h] {report} ...

positional arguments:
  {report}
    report    métricas do piloto a partir do banco local

options:
  -h, --help  show this help message and exit
```

## `qa beta report`

```text
usage: qa beta report [-h] [--since SINCE] [--until UNTIL] [--json] [--out OUT]
                      [--data-dir DATA_DIR]

options:
  -h, --help           show this help message and exit
  --since SINCE        lotes criados a partir de (ISO 8601)
  --until UNTIL        lotes criados antes de (ISO 8601)
  --json               saída em JSON (beta-report.schema.json)
  --out OUT            gravar num arquivo em vez de mostrar
  --data-dir DATA_DIR  pasta de dados (padrão: a desta conta)
```

## `qa backup`

```text
usage: qa backup [-h] {list,now,restore} ...

positional arguments:
  {list,now,restore}
    list              listar as cópias
    now               fazer uma cópia agora
    restore           restaurar uma cópia (com o programa fechado)

options:
  -h, --help          show this help message and exit
```

## `qa backup list`

```text
usage: qa backup list [-h] [--data-dir DATA_DIR] [--backup-dir BACKUP_DIR] [--all]

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR   pasta de dados (padrão: a desta conta)
  --backup-dir BACKUP_DIR
                        pasta das cópias (padrão: backup_dir da configuração)
  --all                 de todas as máquinas e usuários
```

## `qa backup now`

```text
usage: qa backup now [-h] [--data-dir DATA_DIR] [--backup-dir BACKUP_DIR]

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR   pasta de dados (padrão: a desta conta)
  --backup-dir BACKUP_DIR
                        pasta das cópias (padrão: backup_dir da configuração)
```

## `qa backup restore`

```text
usage: qa backup restore [-h] [--data-dir DATA_DIR] [--backup-dir BACKUP_DIR] [--latest] [file]

positional arguments:
  file                  arquivo da cópia

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR   pasta de dados (padrão: a desta conta)
  --backup-dir BACKUP_DIR
                        pasta das cópias (padrão: backup_dir da configuração)
  --latest              a cópia mais nova desta conta
```

## `qa validate-report`

```text
usage: qa validate-report [-h] report

positional arguments:
  report

options:
  -h, --help  show this help message and exit
```
