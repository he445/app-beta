# 0027: Medir o conteúdo, sem a moldura do digitalizador

Status: aceito · Data: 2026-11-19 · Decisores: Everton Ferreira

## Contexto

Na caixa de regressão de 1.000 páginas, 8 das 36 páginas com borda preta ganharam aviso
de desfoque, com correção "redigitalizar": cada uma custaria uma passada no scanner à toa.
A faixa preta mais larga que a margem fixa de 4% entra na máscara de tinta; dentro dela o
Laplaciano é zero e dilui a média, e a mediana da tinta, puxada para o preto, aumenta o
divisor do contraste. Uma página girada com borda passou como de pé, porque a faixa entrava
no recorte central que o classificador de orientação vê.

## Opções consideradas

1. Margem da área útil maior. Corta conteúdo das páginas sem borda e não resolve faixa
   larga.
2. Uma vista de conteúdo, sem as faixas que `black_borders` mede, usada pelas medidas que a
   moldura atrapalha (desfoque, exposição, orientação e, depois de girar, inclinação).
3. Recortar a faixa no próprio arquivo antes da análise. A análise não altera o original
   (princípio do projeto), e a correção de borda é uma decisão do conferente.

## Decisão

Opção 2. `black_borders` continua medindo a página crua. A vista de conteúdo corta cada
faixa acima do `min_fraction` da regra, com 0,5% de folga; sem faixa, é a própria página.
Desfoque, exposição e o classificador de orientação usam a vista; a inclinação usa a vista
já girada de pé. A leitura da numeração continua na página inteira de pé, porque as regiões
são frações da folha. Como defesa para faixa estreita demais, o desfoque também tira da
máscara os componentes de tinta grandes e sólidos. A cadeia de correção (recortar → girar →
endireitar) não muda.

A inclinação também atrapalha o classificador: uma página só inclinada 5,9° foi lida como
de cabeça para baixo com 0,898, a 0,002 da correção automática. Por isso a inclinação é
estimada na vista de conteúdo antes de classificar; acima de 2°, com confiança de pelo menos
0,3, o classificador lê também uma cópia endireitada e vale a leitura mais confiante. Ler só
a endireitada piorou outra página (2,8°, de 0° com 0,77 para 180° com 0,58). De pé, a
inclinação medida antes de classificar é a que a regra `skew` usa.

Faixa abaixo de `min_fraction` não é cortada: na caixa, cortar 11 px de uma linha escura do
topo de uma página sem borda fez o classificador trocar 0° (66%) por 180° (49%).

## Consequências

- Caixa de regressão: zero desfoque falso nas páginas com borda (eram 8); a página girada
  com borda passou a ser achada; borda preta, desfoque e exposição mantiveram os acertos.
- As páginas com borda deixaram de inflar a dispersão do contraste do lote. Uma página de
  tinta cinza, colada no limite (z = −2,0), passou a ganhar "sem contraste": é ruído de
  limiar da regra de exposição, que compara cada página com o lote.
- A página com inclinação acima de 2° (cerca de 4% da caixa) passa pelo classificador duas
  vezes; a de pé não mede a inclinação de novo.
- Cobrança: testes de `content_view` e do desfoque com faixa sólida em `test_detectors.py`;
  testes da leitura endireitada em `test_orientation.py`.
