# Tela de Diagnóstico

Para o suporte e a TI. Mostra os erros do programa, de todas as máquinas quando há uma
pasta compartilhada configurada (`diagnostics_dir`). Nenhum registro tem imagem nem texto
de documento, e caminhos absolutos aparecem como `<caminho>`.

## Ligar

Na máquina, com permissão para gravar a configuração da máquina:

```text
QA-suporte.exe admin token
```

(`QA-suporte.exe`, na pasta do programa, atende os mesmos comandos da linha de comando
`qa` do motor.)

O token aparece **uma única vez**; guarde-o num lugar seguro. Só o hash fica gravado em
`%PROGRAMDATA%\SOSDocs\QA\config.toml`. Reabra o programa: o link **Diagnóstico**
aparece no topo.

## Usar

1. **Diagnóstico** → digite o token (fica só nesta aba; fechar a aba esquece).
2. Cartões: erros nas últimas 24 horas, em 7 dias, máquinas afetadas e erros abertos.
3. Gráfico de erros por dia, por gravidade.
4. Lista agrupada (erros iguais juntos), com quantas vezes, em quais máquinas e versões,
   primeira e última vez. Filtre por versão, máquina, gravidade e estado.
5. Clique num erro para ver a pilha de chamadas e a linha do tempo; **Marcar como
   resolvido** quando corrigir. Se ele voltar a acontecer, reabre sozinho.
6. **Exportar pacote** baixa um zip para anexar num chamado.

Cinco tokens errados seguidos bloqueiam a área por um minuto.
