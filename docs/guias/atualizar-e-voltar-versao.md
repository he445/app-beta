# Atualizar e voltar de versão

A atualização é manual e versionada (SemVer): cada versão é um zip novo. Os dados (banco,
configuração, log) ficam em `%LOCALAPPDATA%\SOSDocs\QA`, fora da pasta do programa, e
continuam valendo de uma versão para outra.

## Atualizar

1. Feche o programa.
2. Renomeie a pasta atual, por exemplo `QA-SOS-Docs-1.0.0` para
   `QA-SOS-Docs-1.0.0-anterior`. **Não apague**: é ela que permite voltar.
3. Extraia o zip da versão nova (confira o SHA-256 publicado com ele) e abra o `QA.exe`.

Ao abrir, se a versão nova precisar mudar o banco (migração), ela primeiro grava uma
cópia em `%LOCALAPPDATA%\SOSDocs\QA\atualizacoes\qa-antes-da-<nova>-de-<anterior>-<data>.sqlite3`
e só depois atualiza. Ficam as cinco cópias mais recentes. A versão aparece no topo da
interface, em `/health` e na tela de Gestão.

## Voltar para a versão anterior

Se a versão nova vier com problema (meta: menos de 5 minutos, sem perder dados):

1. Feche o programa.
2. Abra o `QA.exe` da pasta `...-anterior`.
3. O programa percebe que o banco foi atualizado por uma versão mais nova e, em vez de
   abrir, mostra **Versão anterior do programa** com o botão **Restaurar a cópia de antes
   da atualização**. Clique.
4. Feche a janela e abra o programa de novo.

Nada é apagado: o banco da versão nova fica ao lado, como
`qa.sqlite3.antes-da-restauracao-<data>`. O que foi decidido na versão nova depois da
atualização fica nesse arquivo e não volta sozinho para a versão anterior; ao reinstalar
a versão nova, a TI pode restaurá-lo com `QA-suporte.exe backup restore <arquivo>`.

Sem janela (suporte remoto), o mesmo pela linha de comando, com o programa fechado:

```text
QA-suporte.exe backup restore --before-update
```

A versão anterior nunca abre um banco de versão mais nova: ela para antes de mexer em
qualquer coisa ([backup do banco](../especificacoes/backup-do-banco.md#troca-de-versão)).

## Ver qual máquina ficou para trás

Com a pasta compartilhada de relatórios configurada (`reports_dir`), cada máquina grava
a versão e a última abertura em `maquinas/<computador>.json` ao abrir e a cada hora. A
[Gestão](../operacao/gestao.md) mostra a versão de cada máquina e marca como
**desatualizada** a que está numa versão anterior à mais nova em uso.
