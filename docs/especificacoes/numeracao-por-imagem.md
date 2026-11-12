# Numeração lida da imagem

Como o motor lê a numeração de folha escrita à mão no canto da página quando o lote não
traz `numbering.json`. A saída são as **marcas** que o resolvedor de sequência
([`sequencing.md`](sequencing.md)) já recebe; o resolvedor não muda.

## Quando roda

- O perfil tem `numbering.enabled` e `numbering.read_from_image` (padrão: verdadeiro).
- O lote **não** tem `numbering.json`: o arquivo, quando existe, tem prioridade (lotes
  de conformidade e de demonstração continuam usando o arquivo).
- Os modelos embarcados foram conferidos. Sem eles, a numeração fica ausente e o
  documento cai em `completeness_unverifiable`, como antes.

Roda por página, dentro dos processos de análise, sobre a **vista de pé** a 150 dpi (a
mesma em que a inclinação é medida, já girada quando a página veio de lado).

## Etapas

1. **Região.** Recorte em frações da página `(x0, y0, x1, y1)`; o perfil lista as
   regiões em ordem (`numbering.regions`, padrão `[[0.60, 0.00, 1.00, 0.18]]`, canto
   superior direito). A leitura para na primeira região que tiver número de folha.
2. **Escritos.** O detector (PP-OCRv5_mobile_det, pós-processamento DB) devolve caixas;
   um plano B por limiar adaptativo e componentes conexos acrescenta as caixas que não se
   sobrepõem a nenhuma do modelo (traço fino que o modelo perde). Descartadas: caixa com
   altura abaixo de `numbering.min_height_mm` (padrão 3 mm) e caixa mais larga que 5
   alturas (linha de texto impresso).
3. **Separação.** Caixa com um vão vertical sem tinta de pelo menos 0,35 altura é
   dividida: dois números escritos lado a lado não viram um só ("3 8" não vira "38").
4. **Leituras.** O reconhecedor do perfil (`numbering.recognizer`, padrão
   `ppocrv5-mobile-rec`) devolve até três leituras por caixa, com busca restrita ao
   vocabulário de número de folha (dígitos, `-`, letras de intercalação, `v`). Ficam só as
   leituras com formato de folha (`parse_folio`) e confiança de pelo menos 0,3. Caixa
   sem leitura válida é palavra ou rabisco: não vira marca, mas conta como **escrito**.
   Para cada leitura com 1 ou 7, entra também a alternativa com o dígito trocado (um de
   cada vez), com metade da confiança, se ainda não estiver entre as leituras: a letra de
   mão troca 1 e 7 e o reconhecedor às vezes tem certeza do errado ("72-A" no lugar de
   "12-A"). Ficam as três mais confiáveis; quem escolhe é o resolvedor, pela sequência.
5. **Riscado.** Nota de 0 a 1 por caixa (com margem de 0,3 do tamanho, porque o risco
   costuma passar da caixa): traço quase reto que atravessa pelo menos 85% da largura da
   tinta na faixa do meio, ou dois traços cruzando no centro (X). A marca é riscada com
   nota de pelo menos `numbering.struck_threshold` (padrão 0,6) quando a página tem mais
   de um número; **sozinho na página, exige 0,99** (quem risca escreve o novo ao lado, e o
   traço do meio de um 4 ou de um 7 parece risco).

## Saída

Por página: as marcas (leituras com confiança e se está riscada), se há algum escrito na
região (mesmo ilegível) e o recorte da região em PNG. No relatório, `numbering.source`
diz de onde vieram as marcas (`image` ou `sidecar`) e `numbering.marks` as guarda; a
re-resolução depois de uma numeração digitada (`numbering.typed`) usa essas marcas, sem
ler a imagem de novo. O recorte fica na pasta de trabalho do lote e é servido em
`GET /pages/{id}/numbering-crop`.

## Garantias

- Nenhuma leitura isolada decide: um riscado que escapar ou uma leitura duvidosa é
  decidida pela sequência do documento ou vai para o revisor.
- Determinístico: mesma imagem, mesmos modelos, mesmas marcas.
- Os modelos são carregados uma vez por processo de análise, com uma thread cada.
