# Caixa de regressão

A caixa de regressão mede o motor numa caixa de 1.000 páginas reais com problemas
inseridos, contra um gabarito. Toda mudança de detector roda a caixa antes e depois: a
mudança tem de provar que melhorou o que queria e que não piorou outra regra.

## O que é a caixa

- **12 processos** (`processo 1` a `processo 12`), de 43 a 180 páginas, somando **1.000
  páginas** PNG a 300 dpi, em 16 níveis de cinza, e um `manifest.csv`.
- **Folhas reais:** páginas digitalizadas do RVL-CDIP (cartas, memorandos, formulários,
  manuscritos, faturas, orçamentos, questionários, especificações, e-mails, relatórios,
  currículos), ampliadas de cerca de 91 para 300 dpi. Entraram só as 1.058 em que o motor
  1.1.0 não apontou nenhum problema (`tools/bench_box/folhas-limpas.txt`).
- **Sintéticas:** só as 30 folhas em branco: 20 com papel, gradiente, ruído e poeira; 10
  com a transparência de uma página real espelhada (verso de papel fino).
- **Problemas inseridos,** em posições sorteadas (semente 2026), de 5 a 11 tipos por
  processo:

| Problema | Páginas | Como |
| --- | --- | --- |
| Rotação | 68 | 90°, 180° ou 270° |
| Inclinação | 55 | 1,5° a 6°, para os dois lados |
| Borda preta | 36 | Faixa escura de 3% a 8% em 1 ou 2 lados |
| Desfoque | 34 | Gaussiano, raio de 3 a 5 px a 300 dpi |
| Baixa resolução | 29 | Gravada a 150 ou 200 dpi |
| Duplicata | 25 | Metade cópia exata, metade redigitalizada (deslocada até 1 mm, com ruído) |
| Folha em branco | 30 | 20 comuns e 10 com transparência do verso |
| Exposição | 33 | 18 escurecidas, 15 com a tinta desbotada |
| Arquivo corrompido | 8 | Truncado ou com 0 byte |
| Folha perdida | 3 processos | O `manifest.csv` declara folhas a mais |

15 páginas têm dois problemas juntos. O gabarito (`gabarito_caixa_teste.csv`) tem uma
linha por página, com o problema e os parâmetros; `paginas_perdidas.csv` lista as folhas
perdidas.

## Como gerar

As imagens não ficam no Git: a licença do RVL-CDIP precisa ser conferida antes de
redistribuir. A caixa é reproduzida byte a byte a partir da fonte:

```bash
python3 tools/bench_box/fetch_pool.py tools/bench_box/folhas-limpas.txt folhas
python3 tools/bench_box/build_box.py folhas tools/bench_box/folhas-limpas.txt caixa 2026
```

O zip pronto fica na pasta compartilhada, identificado pelo SHA-256.

## Como rodar e medir

```bash
uv run --project engine qa analyze "caixa/caixa teste" --profile profiles/sos-piloto.yaml \
    --models models --out saida
uv run --project engine python tools/bench_box/time_pages.py "caixa/caixa teste" \
    --profile profiles/sos-piloto.yaml --models models --out saida-serie tempos.json
python3 tools/bench_box/score_box.py --gabarito caixa --report saida/report.json \
    --tempos tempos.json --baseline tools/bench_box/baseline-1.1.0.json \
    --json resultado.json --md resultado.md
```

`time_pages.py` roda a análise em série (`--workers 1`) e cronometra cada página; a
primeira inclui a carga dos modelos e fica fora da mediana. Ele também grava o ângulo de
inclinação medido em cada página, para conferir que uma otimização não mudou a medida.

## O que cada número quer dizer

| Medida | Significado |
| --- | --- |
| Achado / inserido, por problema | A regra certa apontou a página do gabarito |
| Duplicata: par achado | O motor marcou uma das duas páginas do par |
| Duplicata: cópia certa | O motor marcou a cópia do gabarito (a segunda ocorrência) |
| Avisos fora do gabarito | Sinalização numa regra que o gabarito não pede, fora `numbering_review` e o aviso de exposição em página desfocada (o desfoque derruba o contraste) |
| Correção automática em página limpa | Precisa ser zero |
| Lacuna maior que o documento | "Faltam fls." com mais folhas que o próprio processo: leitura de numeração errada |
| Fora de ordem | A caixa nunca embaralha páginas: todo "fora de ordem" é falso |
| Folha perdida | O processo que o `manifest.csv` declara maior foi apontado |
| Tempo | Mediana, percentil 95 e máximo por página em série |

## Como reprova

Comparado com a base (`tools/bench_box/baseline-<versão>.json`), o `score_box.py` sai com
código 1 se: uma regra achar menos que na base; houver menos duplicatas com a cópia certa;
os avisos fora do gabarito subirem mais de 5; aparecer correção automática nova em página
limpa ou lacuna maior que o documento nova; ou a mediana de tempo subir mais de 10%. Com
`--check-skew`, também reprova se o ângulo de inclinação de alguma página mudar mais de
0,05°. A base só é atualizada de propósito, no commit de versão, nunca para fazer um teste
passar.

## Limitações

- **Aviso falso em página limpa está subestimado:** a caixa só tem folhas que o motor 1.1.0
  já achava limpas.
- **Imagens ampliadas:** mais suaves que uma digitalização nativa a 300 dpi, o que mexe com
  desfoque e nitidez.
- **Sem numeração manuscrita:** as folhas do RVL-CDIP não têm número de folha, então os 400
  avisos de numeração ilegível são esperados, e numeração, ordem das folhas e riscado não
  são medidos aqui.
- **Calibração:** um limite novo pode ser escolhido olhando a caixa (fica anotado na
  especificação da regra), mas isso infla o resultado da própria caixa. O número que vale
  para documento real só vem do beta.
