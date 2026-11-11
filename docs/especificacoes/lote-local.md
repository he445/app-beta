# Lote local

Como o motor abre um lote numa pasta do computador ou da rede interna sem copiá-lo e sem
alterá-lo (ADR-0013). Só existe no programa desktop.

## Entrada

`POST /local-batches` com o caminho da pasta (`D:\Lotes\0412` ou
`\\servidor\digitalizacao\0412`), o perfil e, opcionalmente, a estação das páginas cujo
arquivo não identifica a digitalizadora.

## Etapas

```text
1. resolver o caminho
     absoluto; no Windows, forma estendida (\\?\C:\..., \\?\UNC\servidor\...),
     para abrir caminhos com mais de 260 caracteres
     não existe → 404; não é pasta → 422
2. conferir allowed_roots
     lista vazia → qualquer pasta; senão, a pasta precisa estar dentro de uma raiz
     (no Windows sem diferença de maiúsculas nem de tipo de barra) → senão 403
3. contar imagens (TIFF, JPEG, PNG, PDF; sem ocultos) → nenhuma → 422
4. na fila (status queued, stage settling):
     repetir a cada 1 s a lista (caminho, tamanho, data) até ela ficar
     batch_settle_seconds sem mudar
5. stage snapshot: retrato = tamanho, data (ns) e SHA-256 de cada arquivo
     (arquivo ilegível: SHA-256 vazio no retrato)
6. stage analyzing: análise lendo os arquivos no lugar, só para leitura
7. antes de gravar o lote corrigido: comparar com o retrato (ver correções)
```

Arquivos e pastas ocultos (nome começando com `.`) ficam fora do lote e do retrato.

## Falhas

- Arquivo bloqueado por outro programa, sem permissão ou pasta de rede que caiu durante
  a análise: a página vira `corrupted_file` com motivo "arquivo inacessível" e correção
  "abrir o lote de novo" ([corrupted_file](detectors/corrupted_file.md)). O lote segue.
- A pasta não para de mudar: o lote continua esperando; nada é analisado pela metade.

## Garantias

- Nada é escrito na pasta original. A pasta de trabalho do lote (cópias corrigidas,
  retrato, perfil efetivo) fica em `data_dir`.
- A retenção apaga só a pasta de trabalho; a pasta original nunca é apagada.
