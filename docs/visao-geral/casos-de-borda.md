# Casos de borda

O conceito mais importante aqui é separar **defeito de captura** (culpa da digitalização,
exige ação) de **defeito de origem** (o papel já veio assim). Sem essa separação, a
ferramenta reprova lotes corretos e perde a confiança dos garantidores em uma semana.

Por isso a revisão tem a decisão "defeito de origem" (tecla O): registra o problema no
relatório e não reprova o documento.

| Caso | Risco | Tratamento |
| --- | --- | --- |
| Original rasgado, manchado, mofado ou com pedaço faltando | Falso positivo de captura | O revisor marca "defeito de origem"; entra no relatório |
| Papel térmico desbotado (cupom, fax antigo) | Falso positivo de exposição | Idem |
| Verso só com carimbo, rubrica ou assinatura | Remoção indevida como página em branco | Tinta concentrada num ponto vira "quase branca" e nunca é removida automaticamente ([`blank_page`](../especificacoes/detectors/blank_page.md)) |
| Papel colorido ou reciclado | Falso positivo de "escura" ou "sem contraste" | Comparação com a mediana do lote, não com valor fixo ([`exposure`](../especificacoes/detectors/exposure.md)) |
| Duas vias legítimas do mesmo documento | Falso positivo de duplicada | Duplicata só é sinalizada, nunca removida automaticamente ([`duplicate_page`](../especificacoes/detectors/duplicate_page.md)) |
| Numeração do original com erro ("15" repetida, "12-A", volume que recomeça em 1) | Falso positivo de página faltando ou fora de ordem | O resolvedor entende intercalação e repetição ([sequência](../especificacoes/sequencing.md)); o resto é "defeito de origem" |
| Numeração lida com dúvida | Página faltando passa despercebida ou é inventada | Nenhuma leitura isolada é aceita: o documento inteiro decide, e a dúvida vira "revisar numeração", nunca "página faltando" |
| Documento sem numeração e sem contagem declarada | Página faltando é inverificável | O motor diz "completude não verificável" em vez de aprovar |
| Página em paisagem, tabela girada, carimbo inclinado | Falso positivo de inclinação | A inclinação é medida pelas linhas de texto dominantes ([`skew`](../especificacoes/detectors/skew.md)) |
| Lote pequeno | Linha de base pouco confiável | Abaixo de `min_batch_size`, valem os limites absolutos de cada regra |

Casos conhecidos e ainda não tratados: fotografia ou página sem texto, documento pequeno
em página grande, tarja de anonimização, marca d'água e documento em outro idioma. Hoje
caem na revisão humana pela regra que dispararem.
