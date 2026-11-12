# Coleta e relatório do beta

Durante o piloto, a conferência manual continua sendo a oficial. O programa guarda as
confirmações dos garantidores (só neste computador) e calcula as métricas que dizem se
ele pode assumir.

## O que é guardado

Com a coleta ligada no perfil (no perfil do piloto vem ligada), cada numeração digitada
e cada decisão de orientação viram um exemplo: o recorte do canto ou a miniatura da
página, o que o garantidor decidiu e o que o modelo tinha dito. Os exemplos ficam em
`dados\feedback\` dentro da pasta de dados do programa e são apagados depois do prazo
do perfil (`feedback.retention_days`). A coleta depende do aval de quem cuida de LGPD na
empresa.

## Relatório do piloto

No Prompt de Comando, na pasta do programa:

```text
QA-suporte.exe beta report --since 2026-12-01
QA-suporte.exe beta report --since 2026-12-01 --json --out beta-dezembro.json
```

O relatório mostra, para o período: alertas do programa que eram problema de verdade e
os falsos positivos; defeitos que só o garantidor achou; rotações mantidas e desfeitas
(a meta é nenhuma rotação automática desfeita); em quantas páginas a numeração bateu e
quantas precisaram de digitação; páginas que seguiram sem revisão; tempo de análise e
de revisão por lote; e a conferência dos originais (a meta é nenhum alterado). As
definições estão na [especificação](../especificacoes/coleta-do-beta.md).

## Pacote para o ajuste fino

```text
QA-suporte.exe feedback export --out coleta-dezembro.zip --since 2026-12-01
```

O pacote tem imagens de documentos de clientes: guarde e use só dentro da rede da
empresa. O mesmo pacote serve para medir os reconhecedores com a letra real
(`tools/bench_numbering.py`).
