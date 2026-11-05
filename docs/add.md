# ADD — QA Automático de Digitalização (PoC)

Nov 5, 2026 · @Everton Ferreira

## 1. Visão geral

A prova de conceito (PoC) precisa demonstrar, ao vivo, que uma triagem automática reduz em pelo menos 50% as páginas que exigem olho humano, sem deixar passar defeitos críticos.

**Problema.** A meta de 1 milhão de páginas por mês equivale a cerca de 45 mil páginas por dia útil. O controle de qualidade tem 2 garantidores e 1 conferente, sem automação. Conferir 100% manualmente exigiria cerca de 30 páginas por minuto por pessoa, o dia inteiro.

**Proposta.** Um web app: a interface roda no navegador e conversa por API com um motor de análise num servidor, sem nada instalado nos computadores da empresa. Ele recebe uma pasta de lote e, para cada página, documento e lote:

- detecta defeitos de imagem, de sequência e de completude;
- propõe uma correção para cada defeito, aplicável com um clique numa cópia;
- extrai metadados automaticamente (data, equipamento, estação, hash, características técnicas);
- entrega uma tela de revisão rápida só com o que foi sinalizado e um relatório do lote.

**O que a demonstração precisa mostrar.** Uma pasta com cerca de 200 páginas, com defeitos inseridos de propósito, é analisada em cerca de um minuto. A ferramenta sinaliza as páginas problemáticas, o revisor resolve tudo em cerca de 1 minuto e o sistema gera o relatório com a taxa de acerto medida.

**Público.** Supervisão e gestão da SOS DOCS. O objetivo da apresentação é obter permissão para estudar o processo real e rodar um piloto em paralelo.

## 2. Escopo e não-objetivos

A PoC cobre a análise e a revisão de um lote local. Integração, multiusuário e conformidade legal plena ficam para depois do piloto.

| Dentro da PoC | Fora da PoC (fases seguintes) |
| --- | --- |
| Enviar lote pelo navegador (pasta ou .zip com TIFF, JPG, PNG, PDF) | Integração com o software de captura (Kodak, Kofax etc.) |
| Defeitos de imagem por página | Servidor interno de produção e multiusuário com permissões |
| Sequência, páginas faltando, duplicadas, separação de documentos | Geração de PDF/A (a PoC só valida, com o veraPDF) |
| Validação de índice e nomenclatura por regras configuráveis | Assinatura digital ICP-Brasil |
| Metadados automáticos, exportação (JSON, CSV, XMP) e validação PDF/A | Classificação de tipo documental por IA treinada |
| Correções propostas, aplicadas em cópia | Reprocessamento em lote em produção (45 mil páginas/dia) |
| Tela de revisão rápida e relatório do lote | Uso de documentos reais de clientes antes de autorização |

A base de teste da PoC usa apenas documentos próprios, públicos ou gerados, com defeitos inseridos de forma controlada (seção 18).

## 3. Princípios de projeto

Sete regras valem para qualquer decisão técnica. Quando uma funcionalidade conflita com elas, a funcionalidade perde.

1. **Dado real não sai da empresa.** Na PoC, o motor roda em nuvem e só recebe documentos sintéticos ou públicos. No piloto, o mesmo motor roda num servidor da rede interna. Isso resolve LGPD e cláusulas de confidencialidade com clientes.
2. **O original é intocável.** A ferramenta trabalha numa cópia do lote. Toda correção gera um arquivo novo na saída, com registro do que foi alterado.
3. **O humano decide.** A máquina sinaliza, pontua e sugere; aprovar, reprovar ou aplicar correção é sempre uma ação do revisor, registrada com data e hora.
4. **Toda detecção explica a si mesma.** Cada sinalização mostra o motivo, a medida obtida, o limiar usado e, quando possível, a área da página destacada.
5. **Limiar é configuração, não código.** Cada cliente ou tipo de projeto tem um perfil com seus limiares e regras. Calibrar não exige recompilar.
6. **Contrato e especificação antes do código.** O comportamento é definido no contrato (seção 15) e na especificação dos detectores; o código implementa, não define. É isso que permite trocar de linguagem sem mudar o sistema (seção 16).
7. **Sem documentação, não está pronto.** Toda regra, decisão e interface é documentada no repositório, e a integração contínua cobra isso (seção 17).

## 4. Pipeline de processamento

A análise sobe de nível: primeiro cada página, depois cada documento, depois o lote inteiro.

&#91;embedded content: pipeline de processamento · 7 etapas, 1 ciclo de correção\]

A revisão humana fecha o ciclo. Toda correção aplicada gera uma cópia, que é analisada de novo antes de ir para a pasta de saída.

## 5. Catálogo de defeitos de página

São 21 defeitos de página, todos detectáveis com visão computacional clássica e OCR, sem treinar modelo. Os limiares abaixo são pontos de partida e precisam ser calibrados com dados reais no piloto.

Regra geral de calibração: sempre que possível, a medida é comparada com a mediana do próprio lote, e não com um número fixo. Um lote de papel amarelado ou de carbono tem outro "normal".

| Defeito | Como detectar | Limiar inicial | Correção proposta | Severidade |
| --- | --- | --- | --- | --- |
| Desfoque | Variância do Laplaciano em cinza, imagem reduzida a 150 dpi | Abaixo de 40% da mediana do lote | Redigitalizar | Crítico |
| Inclinação | Ângulo das linhas de texto (Hough ou retângulo mínimo dos blocos) | Acima de 0,5° sinaliza; acima de 3° reprova | Endireitar automaticamente (deskew) | Médio |
| Orientação errada (90°/180°) | Detecção de orientação do OCR + projeção das linhas | Confiança acima de 80% | Girar automaticamente | Médio |
| Imagem espelhada | Confiança do OCR baixa no original e alta na versão espelhada | Ganho de confiança acima de 30 pontos | Espelhar automaticamente | Alto |
| Página em branco | Cobertura de tinta após remover bordas e ruído | Abaixo de 0,3%; entre 0,3% e 1% vira "quase branca" | Marcar para remoção, conforme o perfil | Baixo |
| Escura, clara ou sem contraste | Média e desvio do histograma de brilho | Fora de 2 desvios da mediana do lote | Auto-níveis na cópia ou redigitalizar | Alto |
| Conteúdo cortado | Componentes de texto ou desenho tocando a borda | Conteúdo a menos de 2 mm da margem | Redigitalizar | Crítico |
| Bordas pretas | Faixas escuras contínuas nas margens | Faixa acima de 1% da largura | Recorte automático (autocrop) | Baixo |
| Ruído e pontilhado | Contagem de componentes conexos minúsculos por área | Acima de 3 vezes a mediana do lote | Remover pontilhado (despeckle) | Baixo |
| Listras verticais | Perfil de colunas: linha fina contínua na mesma coluna em páginas seguidas | Presente em mais de 80% da altura | Limpar o vidro do scanner; alertar a estação | Alto |
| Canto dobrado | Triângulo ausente ou escuro num canto do contorno da folha | Área acima de 1% da página | Desdobrar e redigitalizar | Alto se cobre conteúdo, senão Baixo |
| Obstrução (grampo, clipe, post-it) | Objeto sobre área de texto, com cor ou textura diferente do papel | Baixa confiança: sempre escala | Remover o objeto e redigitalizar | Alto |
| Furos de perfuração | Círculos (Hough) junto à margem | Diâmetro entre 4 e 8 mm | Preenchimento cosmético, opcional | Baixo |
| Sombra ou curvatura (lombada) | Gradiente de brilho de um lado a outro; linhas de texto curvas | Curvatura acima de 1% da largura | Redigitalizar em mesa plana | Médio |
| Vazamento do verso | Texto espelhado de baixo contraste sob o texto principal | Detectado pela comparação com o verso, quando existe | Remoção de fundo na cópia | Baixo |
| Imagem truncada (atolamento) | Proporção da folha fora do padrão do lote ou faixa esticada | Desvio acima de 5% da proporção esperada | Redigitalizar | Crítico |
| Arquivo corrompido | Falha ao decodificar, 0 byte, páginas ilegíveis no PDF | Qualquer falha | Regerar ou redigitalizar | Crítico |
| Resolução abaixo do exigido | DPI gravado no arquivo contra o DPI do perfil | Abaixo do mínimo do perfil (ex.: 300 dpi) | Reconfigurar o scanner e redigitalizar | Alto |
| Modo de cor incompatível | Imagem P&B quando o perfil exige cor, ou colorida sem conteúdo de cor | Saturação média quase zero em arquivo colorido | Converter para cinza na cópia ou redigitalizar | Médio |
| Folha separadora no arquivo | Patch code ou código de barras de separação | Código reconhecido | Remover a página | Baixo |
| Baixa legibilidade | Confiança média do OCR em áreas de texto impresso | Abaixo de 60 | Redigitalizar com mais resolução ou escalar | Alto |

Texto manuscrito não entra na regra de legibilidade: o OCR naturalmente vai mal nele, e isso não é defeito de captura (seção 9).

## 6. Sequência e completude

Página faltando só é detectável quando existe uma referência do que deveria existir. Sem nenhum sinal, a ferramenta informa "completude não verificável" em vez de aprovar o documento.

### Sinais de referência, do mais ao menos confiável

| Sinal | Como é lido | Confiabilidade |
| --- | --- | --- |
| Numeração impressa ("Página 3 de 12", "3/12") | OCR só nas faixas de cabeçalho e rodapé (10% da altura cada) + expressões regulares | Alta |
| Numeração de folhas manuscrita ou carimbada ("fls. 12", "12-v", "12-A"), às vezes riscada e refeita | Leitor de numeração manuscrita (abaixo), com a sequência resolvida no documento inteiro | Média por página, alta na sequência; é o sinal mais comum nos lotes da SOS |
| Contagem declarada no protocolo ou na folha de preparação do lote | Arquivo de manifesto (CSV) ou campo digitado na abertura do lote | Alta, se o manifesto existir |
| Captura frente e verso | Número de imagens por folha; pares frente/verso pelo nome do arquivo | Média |
| Modelo de tipo documental | Perfil define tipos com número fixo de páginas (ex.: formulário de 2 páginas) | Média |
| Ordem cronológica | Datas extraídas por OCR em documentos de juntada sequencial | Baixa, só sinaliza |
| Continuidade do texto | Frase interrompida no fim da página sem continuação coerente na seguinte | Baixa, só sinaliza |

### Situações detectadas

| Situação | Evidência | Correção proposta |
| --- | --- | --- |
| Página faltando | Lacuna na numeração; contagem menor que a declarada | Localizar a folha no original e redigitalizar; inserir na posição indicada |
| Página fora de ordem | Numeração não crescente dentro do documento | Reordenação automática pela numeração, mostrada como antes e depois |
| Página duplicada | Hash perceptual (dHash) com distância baixa entre páginas; mesma numeração duas vezes | Remover a cópia de pior qualidade |
| Alimentação dupla | Lacuna de exatamente uma folha; alerta do scanner, se gravado nos metadados | Redigitalizar a folha que não foi capturada |
| Dois documentos num arquivo | "Página 1 de" no meio; mudança de nome ou CPF; cabeçalho de primeira página | Dividir o arquivo no ponto indicado |
| Documento partido em dois arquivos | Arquivo que começa em "Página 3 de 5"; continuação do anterior | Juntar os arquivos |
| Documento intruso | Nome ou CPF da página diferente do índice do documento | Mover para o documento ou lote correto |
| Verso esquecido | Folha "12" sem "12-v" quando o perfil exige verso | Redigitalizar o verso |

A reordenação, a divisão e a junção são sempre propostas, nunca aplicadas sem aprovação. Numeração errada no próprio original (duas folhas "15", salto de "20" para "22") é comum em processos e precisa de um botão "defeito de origem" (seção 9).

### Numeração manuscrita, riscada ou múltipla

Nos lotes da SOS a numeração é quase toda manuscrita, às vezes riscada e refeita, ou com mais de um número na mesma folha. Por isso nenhuma leitura isolada é aceita como verdade: cada página gera candidatos, e a sequência do documento inteiro decide.

1. **Recorte.** Analisa só a região onde a numeração costuma ficar (canto superior direito na frente, superior esquerdo no verso), configurável no perfil.
2. **Separação.** Agrupa os traços de tinta da região em candidatos e descarta rubricas e carimbos que não são números. Carimbo numerador impresso vai para o OCR comum.
3. **Detecção de risco.** Para cada candidato, verifica se um traço atravessa o número (linha horizontal ou diagonal, X, rabisco). Combina uma regra geométrica (Hough) com um classificador leve treinado em riscos sintéticos, técnica já usada na pesquisa sobre [texto manuscrito riscado](https://research-repository.rmit.edu.au/articles/conference_contribution/A_deep_learning_approach_to_handwritten_text_recognition_in_the_presence_of_struck-out_text/27590553).
4. **Leitura.** Cada candidato é lido por um modelo de manuscrito: [TrOCR](https://huggingface.co/microsoft/trocr-base-handwritten) (MIT) ou [PaddleOCR-VL 1.6](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6/blob/main/LICENSE) (Apache-2.0). A saída é restrita ao formato de numeração (dígitos, "v" de verso, letra de folha intercalada), e as três leituras mais prováveis ficam guardadas com a confiança de cada uma.
5. **Resolução da sequência.** Um algoritmo de programação dinâmica escolhe, entre os candidatos de todas as páginas, a sequência vigente mais provável: premia incrementos de 1 (ou o padrão frente e verso) e penaliza saltos. Os números riscados formam uma segunda trilha, a numeração anterior, o que identifica renumerações. Uma leitura errada isolada é corrigida pelo contexto, mas fica marcada como inferida.
6. **Decisão.** Página faltando só vira sinalização crítica quando a lacuna é sustentada por leituras confiáveis dos dois lados. Qualquer dúvida vira "revisar numeração", nunca reprovação automática.

| Estado da página | Exemplo | O que a ferramenta faz |
| --- | --- | --- |
| Lido | "12", confiança alta | Aceita |
| Inferido | Lido "17" entre as folhas 11 e 13 | Assume 12, marca como inferido e inclui na amostragem humana |
| Renumerado | "15" riscado e "17" ao lado | Vigente 17, anterior 15; registra a renumeração |
| Ambíguo | Dois números sem risco | Revisão humana |
| Ilegível | Traço sem leitura confiável | Revisão humana |
| Ausente | Nenhuma marca na região | Completude pela contagem declarada ou "não verificável" |

**Revisão.** A tela mostra o canto ampliado com os candidatos e os riscos destacados; o revisor digita o número certo (tecla N). Cada correção vira exemplo rotulado para recalibrar o leitor, e esses exemplos ficam só dentro da empresa.

**Risco declarado.** Esta é a parte de maior risco técnico da PoC: a precisão real só aparece com amostras dos lotes da SOS. Na PoC, o leitor é medido com numeração manuscrita sintética e com folhas numeradas à mão pela própria equipe, sem dado de cliente.

## 7. Validação de indexação e nomenclatura

O índice é lido de um CSV exportado pelo software de captura ou do próprio nome do arquivo, e cada campo é conferido contra regras do perfil e contra o texto da página.

| Verificação | Regra | Correção proposta |
| --- | --- | --- |
| CPF e CNPJ | Dígitos verificadores válidos; o número do índice aparece no texto do documento | Sugerir o número encontrado pelo OCR |
| Nome do titular | Semelhança entre índice e texto (Levenshtein normalizado) de pelo menos 0,85 | Sugerir a grafia encontrada |
| Datas | Data válida, não futura, não anterior a 1900, no formato do perfil | Sugerir a data encontrada na página |
| Campos obrigatórios | Todos os campos exigidos pelo perfil preenchidos | Destacar o campo vazio |
| Nome do arquivo | Segue o padrão do perfil (ex.: `LOTE_CAIXA_DOC_SEQ.pdf`), sem lacunas na sequência e sem caracteres proibidos | Propor o nome correto |
| Estrutura de pastas | Hierarquia lote, caixa e documento conforme o perfil | Indicar a pasta esperada |
| Camada de texto | PDF entregue como pesquisável tem texto extraível | Reprocessar o OCR |
| Conformidade PDF/A | Validação completa com o veraPDF (seção 14) | Apontar a regra violada e reprocessar o arquivo |

Toda sugestão vem com a confiança do OCR e só vale depois que o revisor confirma.

## 8. Metadados automáticos

A ferramenta preenche sozinha os 8 metadados mínimos que o Decreto 10.278/2020 exige para todos os documentos digitalizados: 3 vêm direto do arquivo, 2 da configuração e 3 do conteúdo, como sugestão a confirmar ([texto do Anexo II](https://www2.camara.leg.br/legin/fed/decret/2020/decreto-10278-18-marco-2020-789857-anexo-pe.pdf)).

### Metadados exigidos pelo Decreto (Anexo II, item a)

| Metadado | Fonte automática | Confiabilidade |
| --- | --- | --- |
| Data e local da digitalização (data) | Tag TIFF DateTime, EXIF DateTimeOriginal, CreationDate do PDF ou XMP; na falta, data de modificação do arquivo | Alta pela tag; baixa pela data do arquivo, sempre identificada |
| Data e local da digitalização (local) | Scanner não tem GPS. O local sai de uma tabela do perfil que liga modelo e número de série do scanner, nome do computador ou pasta a "Unidade Campo Grande, Estação 3" | Alta, se a tabela estiver correta |
| Responsável pela digitalização | Pessoa jurídica do perfil (SOS DOCS) + operador, se gravado na tag Artist, no XMP ou no nome do arquivo; senão, informado ao abrir o lote | Média |
| Identificador do documento digital | Gerado no padrão do perfil (ex.: lote-caixa-documento) ou UUID | Alta |
| Hash da imagem | SHA-256 de cada arquivo, calculado localmente | Alta |
| Título | Primeira linha em destaque do documento (OCR) | Sugestão a confirmar |
| Tipo documental | Palavras-chave do perfil ("CONTRATO", "CERTIDÃO", "NOTA FISCAL") | Sugestão a confirmar |
| Autor (emissor) e Assunto | Cabeçalho e CNPJ do emissor; termos mais frequentes do texto | Sugestão a confirmar |

Os 5 metadados adicionais exigidos de órgãos públicos (classe, data de produção, destinação, gênero e prazo de guarda) dependem do plano de classificação do cliente. O perfil pode preenchê-los por regra a partir do tipo documental; a data de produção é sugerida pela primeira data encontrada no documento.

### Metadados técnicos e conformidade com o Anexo I

Também são extraídos: equipamento (tags Make, Model e Software), resolução, modo de cor, profundidade de bits, dimensões em milímetros, tipo de compressão, número de páginas, tamanho e formato. Com eles, a ferramenta confere o padrão técnico mínimo do Anexo I para o tipo documental informado:

| Tipo de documento | Resolução mínima | Cor | Formato |
| --- | --- | --- | --- |
| Texto impresso sem ilustração, P&B | 300 dpi | Monocromático | PDF/A |
| Texto impresso com ilustração, P&B | 300 dpi | Escala de cinza | PDF/A |
| Texto impresso com ilustração e cores | 300 dpi | RGB | PDF/A |
| Manuscrito P&B | 300 dpi | Escala de cinza | PDF/A |
| Manuscrito em cores | 300 dpi | RGB | PDF/A |
| Fotografias e cartazes | 300 dpi | RGB | PNG |
| Plantas e mapas | 600 dpi | Monocromático | PNG |

O Anexo I também exige compressão sem perda. A ferramenta sinaliza arquivos com compressão JPEG com perda dentro de TIFF ou PDF.

**Saída.** Um arquivo JSON por documento, um CSV por lote e os metadados gravados dentro do próprio PDF, em XMP, com o pikepdf. A assinatura ICP-Brasil exigida pelo art. 5º para documentos perante órgãos públicos fica para fase seguinte.

## 9. Casos de borda

O conceito mais importante desta seção é separar **defeito de captura** (culpa da digitalização, exige ação) de **defeito de origem** (o papel já veio assim). Sem essa separação, a ferramenta reprova lotes corretos e perde a confiança dos garantidores em uma semana.

Por isso a revisão tem um botão "defeito de origem": registra o problema no relatório, anexa a evidência e não reprova o documento.

| Caso | Risco | Tratamento |
| --- | --- | --- |
| Original rasgado, manchado, mofado ou com pedaço faltando | Falso positivo de captura | Revisor marca "defeito de origem"; entra no relatório para o cliente |
| Papel térmico desbotado (cupom, fax antigo) | Falso positivo de "clara" e legibilidade | Idem; sugerir digitalização em escala de cinza |
| Verso só com carimbo, rubrica ou assinatura | Remoção indevida como página em branco | Tinta concentrada num ponto vira "quase branca" e nunca é removida automaticamente |
| "Página intencionalmente deixada em branco" | Remoção indevida | Frase reconhecida pelo OCR mantém a página |
| Papel colorido ou reciclado | Falso positivo de "escura" ou "sem contraste" | Comparação com a mediana do lote, não com valor fixo |
| Texto manuscrito | Falso positivo de legibilidade | Áreas manuscritas ficam fora da regra de OCR |
| Documento pequeno (recibo, canhoto, cheque) em página grande | Falso positivo de "quase branca" ou de corte | Detectar o contorno do papel e avaliar só dentro dele |
| Folha grande dobrada (A3, planta) | Metade não capturada passa despercebida | Proporção esperada por tipo documental no perfil |
| Fotografia ou página sem texto | Falso positivo de orientação e legibilidade | Página classificada como "imagem" pula as regras de texto |
| Página em paisagem, tabela girada, carimbo inclinado | Falso positivo de orientação ou inclinação | Usar a orientação dominante do texto; paisagem é legítima |
| Duas vias legítimas do mesmo documento | Falso positivo de duplicada | Duplicata só é sinalizada, nunca removida automaticamente |
| Numeração do original com erro ("15" repetida, "12-A", volume que recomeça em 1) | Falso positivo de página faltando ou fora de ordem | Regras de numeração no perfil + "defeito de origem" |
| Numeração manuscrita ou em posição incomum | Página faltando passa despercebida | Leitor de numeração manuscrita com região configurável (seção 6) |
| Tarja de anonimização | Falso positivo de obstrução ou de "escura" | Retângulo preto sólido de borda reta vira informação, não defeito |
| Marca d'água, tarja "CÓPIA", brasão de fundo | Falso positivo de ruído ou vazamento | Exceção configurável no perfil |
| Post-it com anotação relevante | Informação perdida ou obstrução | Política do contrato: digitalizar com e sem o post-it |
| Documento em outro idioma | OCR ruim, falso positivo de legibilidade | Pacotes de idioma por perfil (português, inglês, espanhol) |
| Lote com 10 mil páginas ou mais | Navegador lento ou sem memória | Processamento incremental, miniaturas em cache, retomada após fechar |

## 10. Motor de correções propostas

Toda sinalização vem com uma proposta de solução, em uma de três classes, conforme o que a correção exige.

| Classe | Exemplos | Como é aplicada |
| --- | --- | --- |
| Automática, na cópia | Endireitar, girar, espelhar, recortar bordas, remover pontilhado, auto-níveis, remover página em branco ou separadora, reordenar pela numeração, dividir ou juntar arquivos, converter colorido sem cor para cinza | Um clique por página ou em massa por tipo; tela de antes e depois; reversível; registrada no log |
| Ação física sugerida | Redigitalizar a folha com a configuração indicada, localizar a folha entre fls. 12 e 14, digitalizar o verso, limpar o vidro do scanner da estação 3 | Vira item da ordem de retrabalho, agrupada por estação e por caixa |
| Escalada para decisão humana | Obstrução, documento intruso, suspeita de defeito de origem, qualquer detecção de baixa confiança | Aparece no topo da fila de revisão com a evidência destacada |

**Correções proibidas.** Algumas correções esconderiam o problema em vez de resolvê-lo, e não podem ser oferecidas: aumentar resolução por interpolação, "clarear" página ilegível até parecer legível e preencher área cortada. Nesses casos a única proposta é redigitalizar.

**Ordem de retrabalho.** Ao fim da revisão, a ferramenta gera uma lista por estação: qual caixa, qual documento, qual folha, o que fazer e com que configuração. Ela é impressa ou exportada em CSV para o setor de digitalização.

**Calibração contínua.** Cada decisão do revisor (sinalização aceita ou rejeitada) fica registrada por regra. Isso mede a precisão real de cada detector e mostra qual limiar precisa subir ou descer.

## 11. Severidade, pontuação e veredito do lote

Cada sinalização tem uma severidade; o pior defeito de um documento decide o estado dele, e a proporção de documentos com problema decide o veredito do lote.

| Severidade | Significado | Exemplos | Efeito |
| --- | --- | --- | --- |
| Crítico | Informação perdida ou ausente | Desfoque, conteúdo cortado, página faltando, arquivo corrompido | Documento reprovado até ser resolvido |
| Alto | Informação em risco ou fora de norma | Resolução abaixo do exigido, listras, obstrução, baixa legibilidade | Exige revisão humana |
| Médio | Corrigível sem redigitalizar | Inclinação, orientação, fora de ordem | Correção automática proposta |
| Baixo | Cosmético | Bordas pretas, pontilhado, furos | Corrigido em massa ou ignorado |

**Estados do documento:** verde (nenhuma sinalização acima de Baixo), amarelo (Médio ou Alto pendente) e vermelho (Crítico pendente).

**Veredito do lote**, com limites configuráveis por perfil:

- **Aprovado:** nenhum vermelho e no máximo 2% de amarelos depois da revisão.
- **Aprovado com ressalvas:** nenhum vermelho, ressalvas e defeitos de origem listados no relatório.
- **Reprovado:** qualquer vermelho pendente; o lote volta com a ordem de retrabalho.

**Amostragem dos verdes.** Mesmo com a triagem, uma amostra aleatória dos documentos verdes (inicialmente 5%) vai para revisão humana. É isso que mede quantos defeitos a ferramenta deixa passar e sustenta a confiança no sistema.

## 12. Interface

A meta de usabilidade é uma decisão por página sinalizada em até 1 segundo, sem tirar a mão do teclado. Visual limpo, com a evidência sempre visível, vale mais que efeitos.

### Telas

1. **Enviar lote.** Arrastar a pasta ou um .zip para o navegador, escolher o perfil do cliente e, opcionalmente, enviar o manifesto (contagem declarada) e o índice em CSV.
2. **Processamento.** Progresso, páginas por segundo e sinalizações aparecendo ao vivo. A revisão pode começar antes de o processamento terminar.
3. **Painel do lote.** Veredito, contagem por severidade e por defeito, percentual de páginas que dispensam revisão e defeitos por estação.
4. **Fila de revisão.** Grade de miniaturas só das páginas sinalizadas, ordenada por severidade, com filtro por tipo de defeito.
5. **Detalhe da página.** Imagem ampliada com a área do defeito destacada, a medida obtida, o limiar, a correção proposta em antes e depois e os metadados da página.
6. **Sequência do documento.** Miniaturas em linha com a numeração lida embaixo de cada uma; lacunas marcadas em vermelho; recorte ampliado do canto com os números riscados destacados; reordenação proposta ou feita arrastando.
7. **Metadados.** Tabela editável por documento, mostrando a fonte e a confiança de cada campo.
8. **Relatório e retrabalho.** Relatório do lote e ordem de retrabalho por estação, exportáveis.
9. **Perfis.** Limiares, regras de numeração, tabela de estações, padrão de nomes e tipos documentais.

### Atalhos da revisão

| Tecla | Ação |
| --- | --- |
| A | Aprovar (sinalização era falso positivo) |
| C | Aplicar a correção proposta |
| R | Reprovar e mandar para retrabalho |
| O | Marcar como defeito de origem |
| Setas | Página anterior ou seguinte |
| Espaço | Ampliar ou reduzir |
| Ctrl+Z | Desfazer a última decisão |
| 1 a 4 | Filtrar por severidade |
| N | Digitar a numeração correta da página |

## 13. Arquitetura

O sistema é um motor de análise local, cercado por adaptadores e exposto por uma API definida em contrato. A interface, a linha de comando e qualquer sistema futuro falam com o motor só por esse contrato, em qualquer linguagem.

**Decisão de implantação (ADR-0001).** A interface é um web app e o motor é um serviço separado, ligados pela API do contrato. Nada é instalado nos computadores da empresa: eles só usam o navegador.

- **Na PoC:** a interface é um site estático (Vercel ou similar) e o motor roda num contêiner Docker num serviço de nuvem (Render, Fly.io, Railway ou Cloud Run; instância de 2 a 4 GB de RAM, sem GPU; preço a confirmar). O acesso exige login e o CORS só aceita o domínio da interface.
- **Dados da PoC:** só lotes sintéticos ou públicos. A tela de envio avisa que documento de cliente é proibido, e o servidor apaga os lotes automaticamente após 24 horas.
- **No piloto:** o mesmo contêiner roda num servidor ou máquina virtual da rede interna, aprovado pela TI. Os documentos reais nunca saem da empresa, e os computadores continuam precisando só do navegador.

O motor de referência é escrito em Python porque é onde estão as melhores ferramentas de visão computacional, OCR e PDF. O que garante a portabilidade não é a linguagem, e sim três coisas fora do código: o contrato (seção 15), a especificação dos algoritmos e a suíte de conformidade (seção 16).

&#91;embedded content: arquitetura da PoC · componentes e o que chama o quê\]

A dependência sempre aponta para dentro: o domínio não conhece nada; os adaptadores conhecem as ferramentas e implementam as portas. Os nomes no código ficam em inglês, com o glossário da seção 17.

| Camada | Responsabilidade | Pode depender de |
| --- | --- | --- |
| Domínio (`domain`) | Entidades, severidade, regras de sequência, pontuação e veredito | Só a própria linguagem |
| Detectores (`detectors`) | Uma função pura por defeito: imagem + parâmetros → achados | Domínio e uma biblioteca de matrizes (NumPy/OpenCV) |
| Aplicação (`application`) | Casos de uso: AnalyzeBatch, ApplyCorrection, RecordDecision, ExportReport | Domínio, detectores e portas |
| Portas (`ports`) | Interfaces: ImageSource, PdfRenderer, OcrEngine, MetadataReader, PdfAValidator, BarcodeReader, Repository, Executor, Clock | Domínio |
| Adaptadores (`adapters`) | Implementações das portas com as ferramentas da seção 14 | Portas e a ferramenta que embrulham |
| Entradas (`entrypoints`) | API HTTP e linha de comando; gRPC no futuro | Aplicação e contrato |

**Estrutura do repositório (monorepo):**

```text
qa-digitalizacao/
├── contracts/          # fonte da verdade: OpenAPI 3.1 + JSON Schema
│   ├── openapi.yaml
│   └── schemas/        # finding, page, document, batch, profile, detector-manifest
├── spec/               # especificação independente de linguagem
│   ├── detectors/      # um .md por detector, algoritmo em pseudocódigo
│   ├── sequencing.md
│   ├── scoring.md
│   └── metadata.md
├── conformance/        # suíte que qualquer implementação precisa passar
│   ├── fixtures/       # imagens e lotes de teste
│   ├── expected/       # achados esperados, em JSON
│   └── tolerances.yaml
├── engine/             # implementação de referência (Python)
│   ├── domain/  detectors/  application/  ports/  adapters/
│   └── entrypoints/    # http/, cli/
├── ui/                 # interface web, cliente gerado do contrato
├── deploy/             # Dockerfile e configuração de nuvem e servidor interno
├── tools/synth/        # gerador da base sintética
└── docs/               # site MkDocs: guias, ADRs, C4, referência
    └── adr/
```

## 14. Ferramentas

Cada função usa a ferramenta que o mercado trata como referência, sempre atrás de uma porta, para poder ser trocada. A regra de licença é: nada AGPL ou GPL ligado ao núcleo; ferramentas GPL rodam como processo externo, o que preserva a opção de um produto fechado no futuro.

| Função | Escolha | Licença | Motivo e alternativa |
| --- | --- | --- | --- |
| Linguagem do motor | Python 3.12+ | PSF | Todas as bibliotecas abaixo têm Python como interface principal. Trechos críticos podem migrar para Rust ou C++ seguindo a mesma especificação |
| Ambiente e dependências | uv | MIT / Apache-2.0 | Lockfile reproduzível e instalação rápida. Alternativa: Poetry |
| Imagens grandes | libvips (pyvips) | LGPL-2.1 | Abre TIFF multipágina enorme com pouca memória e é bem mais rápido que Pillow |
| Visão computacional | OpenCV 4 | Apache-2.0 | Padrão da indústria para Laplaciano, Hough, morfologia e componentes. Alternativa: scikit-image |
| Renderizar PDF | pypdfium2 (PDFium, o motor do Chrome) | Apache-2.0 / BSD-3 | Rápido e permissivo. O PyMuPDF é mais completo, mas é [AGPL ou licença comercial](https://pypi.org/project/PyMuPDF/1.19.0/) |
| Ler e gravar PDF e XMP | pikepdf (qpdf) | MPL-2.0 | Grava metadados XMP sem reprocessar as imagens |
| Validar PDF/A | [veraPDF](https://verapdf.org/home/) | GPLv3+ ou MPLv2+ | Validador de referência do setor, mantido pela PDF Association e pela Open Preservation Foundation. Roda como processo externo (Java) |
| OCR rápido e orientação | Tesseract 5 (tesserocr) | Apache-2.0 | Leve, roda em CPU, mais de 100 idiomas e detecção de orientação |
| OCR de alta precisão | [PaddleOCR 3.x](https://pasqualepillitteri.it/de/news/25571/beste-lokale-ocr-pc-server) (PP-OCRv5) | Apache-2.0 | Referência aberta em precisão; versão 3.6 de maio de 2026. Alternativa comercial: ABBYY FineReader Engine, como outro adaptador |
| Metadados de imagem | ExifTool (via PyExifTool) | GPL ou Artistic | Lê praticamente toda tag de TIFF, EXIF, XMP e PDF. Roda como processo externo |
| Código de barras e patch code | zxing-cpp | Apache-2.0 | Leitor 1D e 2D rápido, com bindings em várias linguagens. Alternativa: pyzbar |
| Comparação de texto | RapidFuzz | MIT | Distância de Levenshtein rápida para conferir índice contra OCR |
| API HTTP | FastAPI + Pydantic v2 | MIT | Modelos gerados a partir do contrato e validação automática. Alternativa: Litestar |
| Armazenamento | SQLite com migrações em SQL puro | Domínio público | Um arquivo, legível por qualquer linguagem, sem ORM preso ao Python. Em servidor: PostgreSQL |
| Paralelismo | Pool de processos atrás da porta Executor | PSF | Usa todos os núcleos sem infraestrutura. Em escala: Ray ou Celery |
| Interface | React + TypeScript + Vite, TanStack Query, OpenSeadragon | MIT / BSD-3 | Padrão de mercado; OpenSeadragon dá zoom profundo em páginas de 300 a 600 dpi |
| Cliente da API | openapi-typescript | MIT | Tipos da interface gerados do contrato, sem divergência |
| Implantação | Docker para o motor; interface em site estático | Apache-2.0 | Nada instalado nos computadores; o mesmo contêiner vai da nuvem (PoC) para o servidor interno (piloto) |
| Testes | pytest + Hypothesis | MIT / MPL-2.0 | Testes de propriedade encontram casos de borda sozinhos |
| Qualidade de código | Ruff, mypy em modo estrito, pre-commit | MIT | Padrão do Python moderno |
| Contrato | Spectral (lint) + oasdiff (quebra de compatibilidade) | Apache-2.0 | O contrato é validado e versionado na integração contínua |
| Documentação | MkDocs Material, mkdocstrings, Structurizr ou Mermaid (C4), Scalar (OpenAPI) | MIT / Apache-2.0 | Documentação como código, versionada junto com o repositório. Alternativa: Docusaurus |
| Numeração manuscrita | TrOCR (manuscrito) ou PaddleOCR-VL 1.6 em versão quantizada para CPU; risco detectado com OpenCV + classificador leve | MIT; Apache-2.0 | Lê só os recortes do canto da página, o que mantém o custo baixo sem GPU. O classificador de risco é treinado com riscos sintéticos sobre dígitos manuscritos |

As licenças precisam ser revistas por alguém do jurídico antes de qualquer distribuição comercial.

## 15. Contratos e modelo de dados

O contrato em OpenAPI 3.1 e JSON Schema 2020-12 é a fonte da verdade: os modelos Python, os tipos TypeScript e qualquer implementação futura são gerados a partir dele ou validados contra ele, nunca o contrário.

**Regras do contrato:**

- Versionado com SemVer; uma mudança incompatível exige versão maior, e o oasdiff bloqueia a integração contínua se isso não acontecer.
- Nomes em inglês e campos em `snake_case`.
- Unidades sempre explícitas: coordenadas em pixels com origem no canto superior esquerdo, ângulos em graus (positivo = sentido horário), resolução em dpi, datas em ISO 8601 UTC, números reais em float64.
- Tipos fechados por enumeração (severidade, regra, decisão), nunca texto livre.
- Cada detector declara um manifesto com identificador, versão, parâmetros e saída.

**Entidades:** Profile (perfil), Batch (lote), Document, Page, Finding (sinalização), Correction, Decision e MetadataField. Exemplo do esquema de uma sinalização:

```yaml
$schema: https://json-schema.org/draft/2020-12/schema
$id: finding.schema.json
title: Finding
type: object
required: [id, target, rule, rule_version, severity, measure, threshold, confidence, correction]
properties:
  id: { type: string, format: uuid }
  target:
    type: object
    required: [kind, id]
    properties:
      kind: { enum: [page, document, batch] }
      id: { type: string }
  rule: { type: string, pattern: "^[a-z0-9_]+$" }   # blur, skew, missing_page...
  rule_version: { type: string }                    # versão SemVer do detector
  severity: { enum: [critical, high, medium, low] }
  measure: { type: number }
  threshold: { type: number }
  confidence: { type: number, minimum: 0, maximum: 1 }
  region:                                           # pixels, origem no canto superior esquerdo
    type: object
    properties: { x: { type: integer }, y: { type: integer }, w: { type: integer }, h: { type: integer } }
  correction: { $ref: correction.schema.json }
  decision: { $ref: decision.schema.json }
```

Manifesto de um detector:

```yaml
id: blur
version: 1.0.0
spec: spec/detectors/blur.md
input: page_gray_150dpi
params:
  relative_threshold: { type: number, default: 0.4 }   # fração da mediana do lote
output: finding
severity: critical
```

**API (resumo do OpenAPI):**

| Rota | Função |
| --- | --- |
| `POST /batches` | Enviar um lote (upload em partes), com perfil e manifesto |
| `GET /batches/{id}` | Estado, progresso e veredito |
| `GET /batches/{id}/events` | Progresso em tempo real (Server-Sent Events) |
| `GET /batches/{id}/findings` | Sinalizações filtradas por severidade e regra |
| `POST /findings/{id}/decision` | Aprovar, corrigir, reprovar ou marcar defeito de origem |
| `GET /pages/{id}/image` | Imagem original ou corrigida, em tiles para zoom |
| `GET /documents/{id}/metadata` | Metadados com fonte e confiança |
| `POST /batches/{id}/exports` | Relatório, CSV, JSON e ordem de retrabalho |
| `GET /profiles`, `PUT /profiles/{id}` | Perfis validados contra o esquema |
| PUT /pages/{id}/numbering | Confirmar ou corrigir a numeração lida |

A linha de comando expõe os mesmos casos de uso, por exemplo `qa analyze ./lote --profile cliente.yaml --out ./saida`, o que permite rodar a suíte de conformidade e integrar com o software de captura sem interface.

## 16. Portabilidade entre linguagens

Portar o motor para outra linguagem deve ser trabalho mecânico: reimplementar funções a partir de uma especificação e provar equivalência rodando a mesma suíte de testes. Seis mecanismos garantem isso.

1. **Especificação antes do código.** Cada detector tem um documento em `spec/detectors/` com objetivo, entrada, algoritmo em pseudocódigo sem depender de biblioteca, parâmetros, saída, falhas conhecidas e referências. O código Python é a implementação de referência, não a especificação.
2. **Tipos gerados do contrato.** Os modelos de cada linguagem saem do JSON Schema por geradores (datamodel-code-generator, openapi-typescript, openapi-generator, quicktype). Ninguém reescreve tipo à mão.
3. **Suíte de conformidade independente de linguagem.** A pasta `conformance/` tem imagens e lotes de teste, os achados esperados em JSON e um arquivo de tolerâncias (por exemplo: ângulo ±0,1°, medidas relativas ±2%, mesmo conjunto de regras disparadas). Cada linguagem tem um executor fino que roda a implementação e compara. Uma implementação só substitui outra quando passa 100%.
4. **Determinismo.** Nada aleatório; versões de modelos de OCR fixadas por hash; ordem de processamento definida; regras de arredondamento escritas na especificação. A mesma entrada gera a mesma saída em qualquer máquina.
5. **Fronteiras finas com o mundo.** O núcleo não faz entrada e saída; os adaptadores são pequenos. Portar significa reescrever o núcleo e escolher adaptadores equivalentes na linguagem nova (tabela abaixo).
6. **Troca gradual.** Como cada detector é independente e o motor fala por contrato, dá para portar um detector por vez e rodar as duas versões em paralelo, comparando resultados, sem parar a operação.

**Adaptadores equivalentes por linguagem** (exemplos a validar no momento da migração):

| Porta | Python (referência) | C# / .NET | Java | Rust | Navegador (WebAssembly) |
| --- | --- | --- | --- | --- | --- |
| Visão computacional | OpenCV | OpenCvSharp | OpenCV Java | opencv-rust | OpenCV.js |
| OCR | Tesseract, PaddleOCR | Tesseract (NuGet), PaddleOCRSharp | Tess4J | leptess | Tesseract.js, PaddleOCR.js |
| Renderizar PDF | pypdfium2 | PDFium | Apache PDFBox | pdfium-render | pdf.js |
| Validar PDF/A | veraPDF (processo) | veraPDF (processo) | veraPDF (biblioteca) | veraPDF (processo) | não se aplica |
| Código de barras | zxing-cpp | ZXing.Net | ZXing | rxing | zxing-wasm |
| Armazenamento | SQLite | SQLite | SQLite | SQLite | IndexedDB ou sql.js |

A última coluna mostra que até a ideia original, tudo no navegador, continua possível: a mesma especificação e a mesma suíte de conformidade validariam uma versão WebAssembly do motor.

## 17. Documentação

Nada está pronto sem documentação, e isso é cobrado pela integração contínua: o build falha se uma regra registrada não tiver especificação, manifesto e casos de conformidade.

**Definição de pronto** para qualquer mudança: código, testes, especificação atualizada, manifesto válido, caso de conformidade, docstring nas funções públicas e entrada no CHANGELOG.

| Documento | Onde fica | Como é cobrado |
| --- | --- | --- |
| Especificação de detector | `spec/detectors/<id>.md`, modelo obrigatório | Teste falha se uma regra registrada não tiver o arquivo |
| Manifesto de detector | `engine/detectors/<id>/manifest.yaml` | Validado contra o JSON Schema na integração contínua |
| Contrato | `contracts/` | Spectral (lint) e oasdiff (bloqueia quebra sem versão maior) |
| Decisões de arquitetura (ADR) | `docs/adr/NNNN-titulo.md`, formato MADR | Mudança de porta, dependência ou contrato exige ADR no mesmo PR |
| Diagramas C4 (contexto, contêiner, componente) | `docs/architecture/`, como código (Structurizr ou Mermaid) | Gerados no build do site |
| Referência da API | Gerada do OpenAPI (Scalar) | Automática no build |
| Referência do código | Docstrings estilo Google + mkdocstrings | Regra de docstring do Ruff em funções públicas |
| Guias | `docs/guides/`: instalar, rodar a demonstração, criar detector, portar para outra linguagem | Verificação de links no build |
| Glossário | `docs/glossary.md` | Revisado quando surge termo novo |
| Histórico | CHANGELOG (Keep a Changelog) + Conventional Commits | Gerado a partir dos commits |

**Modelo de especificação de detector:**

```markdown
# blur: Desfoque
Versão: 1.0.0 · Severidade padrão: crítico

## Objetivo
## Entrada (formato, resolução, espaço de cor)
## Algoritmo (pseudocódigo, sem citar bibliotecas)
## Parâmetros (nome, tipo, padrão, faixa válida)
## Saída (campos do Finding preenchidos)
## Falhas conhecidas e casos de borda
## Casos de conformidade (conformance/fixtures/blur/)
## Referências
## Histórico de versões
```

**ADRs iniciais:**

1. ADR-0001: Interface web e motor Python em servidor, ligados por API; nada instalado nos computadores da empresa.
2. ADR-0002: OpenAPI + JSON Schema como fonte da verdade (Protobuf avaliado e adiado).
3. ADR-0003: Arquitetura hexagonal, núcleo sem entrada e saída.
4. ADR-0004: Política de licenças, nada AGPL ou GPL ligado ao núcleo.
5. ADR-0005: SQLite com SQL puro, sem ORM.
6. ADR-0006: Código em inglês, documentação em português, com glossário.

**Glossário (domínio em português, código em inglês):**

| Português | Código |
| --- | --- |
| Lote | Batch |
| Documento | Document |
| Página | Page |
| Sinalização | Finding |
| Correção proposta | Correction |
| Decisão do revisor | Decision |
| Perfil do cliente | Profile |
| Severidade | Severity |
| Veredito | Verdict |
| Defeito de origem | SourceDefect |
| Ordem de retrabalho | ReworkOrder |

## 18. Base de teste e métricas de sucesso

A PoC é avaliada numa base sintética de cerca de 2 mil páginas, em que cada defeito é inserido por script. Assim o gabarito é conhecido e a taxa de acerto é medida, não estimada.

**Montagem da base.** Páginas limpas de documentos próprios, de domínio público e de documentos fictícios gerados (com CPFs fictícios válidos e numeração "Página X de Y" e "fls. N"). Um script aplica defeitos com parâmetros conhecidos em cerca de 25% delas: desfoque, rotação, inclinação, corte, bordas pretas, escurecimento, listra vertical, canto dobrado, retângulo de post-it, espelhamento, redução de resolução, compressão com perda, página removida, páginas trocadas, duplicada e branca inserida. A numeração das folhas é manuscrita sintética (dígitos manuscritos de bases públicas, com números riscados, refeitos e duplicados), complementada por folhas numeradas à mão pela equipe. Cada alteração gera uma linha no gabarito em JSON, que também alimenta a suíte de conformidade (seção 16).

**Metas para considerar a PoC aprovada:**

| Métrica | Meta |
| --- | --- |
| Defeitos críticos encontrados (recall) | 98% ou mais |
| Todos os defeitos encontrados (recall) | 95% ou mais |
| Sinalizações corretas (precisão) | 70% ou mais |
| Páginas que dispensam revisão humana | 50% ou mais |
| Página faltando encontrada, quando há numeração | 95% ou mais |
| Velocidade num servidor de 4 núcleos sem GPU, com leitura da numeração | 3 páginas por segundo ou mais (a confirmar) |
| Tempo para revisar o lote da demonstração (200 páginas) | 2 minutos ou menos |
| Numeração manuscrita lida corretamente, por página | 90% ou mais antes da correção pela sequência |
| Números riscados identificados | 90% ou mais |

Precisão de 70% é aceitável porque um falso positivo custa cerca de 1 segundo de revisão; um falso negativo custa um documento errado entregue ao cliente. Por isso o recall vem primeiro.

## 19. Riscos e limitações

O maior risco é a PoC parecer melhor do que é: defeitos sintéticos são mais limpos que os reais, então os números da base sintética são um teto, e só o piloto com lotes reais decide.

| Risco ou limitação | Mitigação |
| --- | --- |
| Resultados sintéticos otimistas | Piloto em paralelo com lote real já conferido; comparar com o que os humanos acharam |
| Página faltando sem numeração nem manifesto é inverificável | Status "completude não verificável"; propor manifesto de contagem na preparação |
| O tempo dos garantidores pode estar em erros de contexto (índice, documento errado), não de imagem | Diagnóstico antes do piloto: medir onde o tempo vai |
| Contrato pode exigir conferência humana de 100% | O ganho vira revisão assistida (mais rápida), não dispensa de revisão |
| Falsa sensação de segurança | Amostragem obrigatória dos verdes e relatório de defeitos que escaparam |
| Nada pode ser instalado nos computadores da empresa | Web app: os computadores só usam o navegador; o motor roda em nuvem na PoC e num servidor interno no piloto |
| O software de captura já faz parte da triagem | Mapear as funções dele no diagnóstico e não duplicar |
| Dados de clientes | Nenhum documento real antes de autorização formal; a partir do piloto, processamento só no servidor interno |
| Propriedade do código | PoC feita fora do expediente, com equipamento e dados próprios; acordo escrito antes da adaptação interna |
| Licença de ferramenta incompatível com produto comercial | Política do ADR-0004: ferramentas GPL só como processo externo; revisão jurídica antes de distribuir |
| Escopo maior que a versão no navegador (contrato, conformidade, documentação) | Prazo da PoC revisto para 4 a 6 semanas; começar pelos 5 detectores mais comuns e pela numeração, e completar os outros no piloto |
| Documento real enviado ao servidor da PoC | Aviso na tela de envio, login, apagamento automático em 24 horas e lotes de demonstração já carregados no servidor |
| Numeração manuscrita lida errada | Sequência resolvida no documento inteiro; dúvida vira "revisar numeração", nunca "página faltando" (seção 6) |

## 20. Roadmap e roteiro da demonstração

A PoC leva de 4 a 6 semanas fora do expediente; cada fase seguinte só começa quando a anterior bate seu critério.

&#91;embedded content: roadmap · 4 fases, 3 critérios de passagem\]

O piloto só começa com autorização formal e acordo escrito sobre o código; a implantação só começa se a ferramenta achar 98% dos defeitos críticos num lote real.

### Roteiro da demonstração (cerca de 5 minutos)

1. Mostrar a pasta com 200 páginas e dizer quantas têm defeito inserido, sem dizer quais.
2. Arrastar o lote para o navegador. Em cerca de um minuto, o painel mostra o veredito e quantas páginas dispensam revisão.
3. Revisar a fila pelo teclado: aplicar correções automáticas, mandar duas folhas para retrabalho, marcar uma como defeito de origem.
4. Abrir a sequência de um documento com numeração manuscrita, um número riscado e refeito, uma folha faltando e outra fora de ordem; aceitar a reordenação proposta.
5. Mostrar os metadados preenchidos sozinhos, com a fonte de cada um.
6. Exportar o relatório e a ordem de retrabalho.
7. Fechar com o gabarito: quantos defeitos a ferramenta encontrou, quantos deixou passar e o tempo total da revisão.
8. Fazer o pedido: acompanhar os garantidores por 1 a 2 dias e rodar um piloto em paralelo num lote real já conferido.

## Fontes

- [Decreto nº 10.278/2020, texto original (Câmara dos Deputados)](https://www2.camara.leg.br/legin/fed/decret/2020/decreto-10278-18-marco-2020-789857-publicacaooriginal-160146-pe.html)
- [Decreto nº 10.278/2020, Anexos I e II (Câmara dos Deputados)](https://www2.camara.leg.br/legin/fed/decret/2020/decreto-10278-18-marco-2020-789857-anexo-pe.pdf)
- [Comparativo de OCR local em 2026: PaddleOCR 3.6, Tesseract (Apache-2.0)](https://pasqualepillitteri.it/de/news/25571/beste-lokale-ocr-pc-server)
- [PaddleOCR 3.0 Technical Report: toolkit sob licença Apache](https://fugumt.com/fugumt/paper_check/2507.05595v1_enmode)
- [PaddleOCR-VL 1.6: licença Apache-2.0 (Hugging Face)](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6/blob/main/LICENSE)
- [TrOCR base handwritten: modelo de manuscrito, licença MIT (Hugging Face)](https://huggingface.co/microsoft/trocr-base-handwritten)
- [Reconhecimento de manuscrito com texto riscado e treino com riscos sintéticos (RMIT)](https://research-repository.rmit.edu.au/articles/conference_contribution/A_deep_learning_approach_to_handwritten_text_recognition_in_the_presence_of_struck-out_text/27590553)
- [veraPDF: validador PDF/A, licença dupla GPLv3+ e MPLv2+](https://verapdf.org/home/)
- [PyMuPDF: licença AGPL ou comercial (PyPI)](https://pypi.org/project/PyMuPDF/1.19.0/)
