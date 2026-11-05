# 0007: Lote de conformidade gerado de forma determinística

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

O ADD prevê imagens de teste em `conformance/fixtures/`. Páginas realistas têm ruído de
papel, que não comprime: o lote mínimo (30 páginas A5 a 300 dpi) ocupa ~58 MB.

## Opções consideradas

1. Versionar as imagens (Git LFS ou não).
2. Imagens sem ruído (pequenas, mas irrealistas: os detectores ficariam calibrados no vazio).
3. Gerar o lote com `tools/synth` (semente fixa) e versionar só o gabarito.

## Decisão

Opção 3. `conformance/expected/core.json` é versionado; o teste gera o lote, confere que
o gabarito gerado é idêntico ao versionado e só então compara o relatório. O gabarito
descreve o que foi inserido (regra, alvo, parâmetros), não o que o motor achou: a
conformidade não é circular.

## Consequências

- Mudança no gerador quebra o teste até o gabarito ser atualizado no mesmo PR.
- Pixels podem variar entre máquinas (fontes, versão do zlib); o gabarito não depende de
  pixels, só dos defeitos inseridos, e as tolerâncias ficam em `tolerances.yaml`.
- Os casos de sequência são JSON puro e versionados em `fixtures/sequencing/`.
