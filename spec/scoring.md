# Severidade, estado do documento e veredito

Versão: 1.0.0

## Pendência

Uma sinalização está **pendente** sem decisão ou com decisão `reject` (R). `approve` (A,
falso positivo), `correct` (C) e `source_defect` (O, defeito de origem) a resolvem.

## Estado do documento

Considera as sinalizações de página das suas páginas e as de documento.

```text
pior ← maior severidade pendente
vermelho se pior = crítico; amarelo se pior ∈ {alto, médio}; verde caso contrário
```

## Veredito do lote

```text
reprovado se algum documento está vermelho
aprovado se amarelos/total ≤ max_yellow_ratio, sem defeito de origem
         e sem sinalização de lote pendente de severidade ≥ médio
aprovado com ressalvas nos demais casos (inclusive lote vazio)
```

## Amostragem dos verdes

```text
n ← teto(green_sample_ratio × quantidade de verdes)
amostra ← os n verdes de menor SHA-256(lote + "/" + documento) em hexadecimal,
          devolvidos em ordem crescente de identificador
```

Sem aleatoriedade: a mesma entrada gera a mesma amostra.

## Páginas que exigem revisão

Uma página exige olho humano quando tem sinalização de severidade ≥ médio, ou pertence a
um documento com sinalização de documento ≥ médio, ou a um documento da amostra dos
verdes. Sinalizações baixas são tratadas em massa. A meta da PoC é que ≥ 50% das páginas
dispensem revisão.

## Parâmetros (perfil, seção `verdict`)

| Nome | Padrão |
| --- | --- |
| `max_yellow_ratio` | 0,02 |
| `green_sample_ratio` | 0,05 |
