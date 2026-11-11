<!-- Gerado por tools/docs/gen_reference.py. Não edite: mude a fonte e gere de novo. -->

# Referência da linha de comando

O comando `qa` usa os mesmos casos de uso da API, sem interface. Rode com
`uv run --project engine qa <comando>`.

## `qa`

```text
usage: qa [-h] [--version] {analyze,rules,validate-profile,admin,validate-report} ...

QA automático de digitalização

positional arguments:
  {analyze,rules,validate-profile,admin,validate-report}
    analyze             analisar um lote local
    rules               listar as regras registradas
    validate-profile    validar um perfil contra o contrato
    admin               administração desta máquina
    validate-report     validar um report.json contra o contrato

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## `qa analyze`

```text
usage: qa analyze [-h] [--profile PROFILE] --out OUT [--workers WORKERS] [--quiet] batch

positional arguments:
  batch              pasta do lote

options:
  -h, --help         show this help message and exit
  --profile PROFILE  perfil YAML do cliente
  --out OUT          pasta de saída
  --workers WORKERS  processos (1 = em série)
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

## `qa validate-report`

```text
usage: qa validate-report [-h] report

positional arguments:
  report

options:
  -h, --help  show this help message and exit
```
