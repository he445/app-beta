# corrupted_file: Arquivo corrompido

Versão: 1.1.0 · Severidade padrão: crítico

## Objetivo

Garantir que nenhum arquivo ilegível passe despercebido nem interrompa o lote.

## Entrada

Resultado da decodificação (porta `ImageSource`).

## Algoritmo

```text
se o arquivo tem 0 byte, não abre, ou uma página falha ao decodificar:
    sinaliza a página (ou a página 0 do arquivo, se nem a contagem de páginas foi lida)
    measure = 1, threshold = 0, confiança 1
```

A mensagem traz o motivo da falha sem caminhos do computador.

Falha de **acesso** não é defeito do arquivo: arquivo bloqueado por outro programa, sem
permissão de leitura ou numa pasta de rede que caiu durante a análise. Nesses casos o
motivo é "arquivo inacessível", a página continua sinalizada como crítica (não foi
verificada) e a correção muda (ver Saída). O lote nunca é interrompido.

## Parâmetros

Nenhum.

## Saída

- Arquivo corrompido: correção `physical/regenerate`, regerar no software de captura ou
  redigitalizar.
- Arquivo inacessível: correção `escalate/human_review`, fechar o programa que usa o
  arquivo (ou conferir a rede e a permissão) e abrir o lote de novo.

## Falhas conhecidas e casos de borda

- PDF que abre mas tem uma página com conteúdo inválido pode renderizar em branco sem
  erro; nesse caso a página cai em [`blank_page`](blank_page.md).
- A validação PDF/A (veraPDF) é outra regra, prevista para a fase seguinte.

## Referências

- Decreto 10.278/2020, art. 5º (integridade do documento digitalizado).

## Casos de conformidade

`conformance/fixtures/core`: `CX001/DOC0006/0004.tif` (truncado), `CX001/DOC0006/0005.tif`
(0 byte).

## Histórico de versões

- 1.1.0: arquivo inacessível (bloqueado, sem permissão, rede fora) tem correção própria.
- 1.0.0: versão inicial.
