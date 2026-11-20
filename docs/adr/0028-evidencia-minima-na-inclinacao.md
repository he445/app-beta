# 0028: Evidência mínima para sinalizar e corrigir a inclinação

Status: aceito · Data: 2026-11-19 · Decisores: Everton Ferreira

## Contexto

A regra `skew` propunha endireitamento automático para qualquer ângulo acima de
`flag_threshold`, sem olhar a confiança que a própria estimativa calcula
(`2 × (pontuação do ângulo − pontuação de 0°) / pontuação do ângulo`). Na caixa de regressão
de 1.000 páginas, uma página limpa recebeu correção automática de 1,90° com confiança 0, e
outra de 0,60° com confiança 0,06: o motor não tinha evidência e alterava a página sozinho.
O mesmo número também decide se a página é endireitada antes de classificar a orientação
(ADR-0027).

## Opções consideradas

1. Subir `flag_threshold`. Deixa passar inclinação real pequena, que o Decreto 10.278 não
   aceita.
2. Usar a confiança em dois degraus: abaixo de um mínimo, não sinalizar; num degrau
   intermediário, sinalizar só para revisão; acima, correção automática como hoje.

## Decisão

Opção 2 ([especificação](../especificacoes/detectors/skew.md)). `min_flag_confidence` = 0,1:
abaixo dele o ângulo achado pontua praticamente igual a 0° e nada é sinalizado.
`min_auto_confidence` = 0,3: entre os dois, a correção vai para revisão
(`params.review`), fora do "Corrigir tudo". O mesmo 0,3 é o mínimo para endireitar a página
antes de classificar a orientação (`orientation.deskew_min_confidence`): numa página de lado
a busca de ângulo não acha linhas e a confiança fica baixa.

## Consequências

- Caixa de regressão: as duas correções automáticas sem evidência somem; as 55 inclinações
  inseridas continuam achadas como antes (53).
- Continua uma correção automática em página limpa: 0,55° com confiança 0,67, colada no
  `flag_threshold`. É ruído de limiar, não falta de evidência.
- Cobrança: teste dos dois degraus em `test_detectors.py`.
