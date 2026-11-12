# Interface de revisão

Guia para garantidores e conferentes. Para instalar e publicar, veja
[Desenvolver a interface](../guias/desenvolver-interface.md).

## Fluxo

1. **Entrar.** No programa desktop não há tela de entrada: seu usuário do Windows vai em
   cada decisão. Na demonstração, digite seu nome. Se o motor estiver dormindo, a tela
   mostra "Acordando o motor de análise…" e segue sozinha (até ~1 minuto no plano
   gratuito). O token só é pedido quando o motor exige (`QA_API_TOKEN`).
2. **Abrir lote** (programa desktop): cole o caminho da pasta, local ou de rede
   (`\\servidor\digitalizacao\0412`), ou use **Escolher pasta…**. Escolha o perfil e, se
   os arquivos não disserem de qual digitalizadora vieram, a estação. A pasta é lida no
   lugar e nunca alterada. Enquanto a digitalizadora ainda grava, o lote aparece como
   "Esperando a pasta parar de mudar".
   **Caixa em conferência noutra máquina:** se outra pessoa estiver com a caixa aberta,
   o programa avisa quem, em qual máquina e desde quando, e não abre. Se essa máquina
   parou de dar sinal há mais de dez minutos (o programa fechou ou caiu), aparece
   **Assumir a caixa**: assumir fica registrado com seu nome. Se alguém assumir uma
   caixa que você estava conferindo, o painel do lote avisa. A caixa fica com você até
   ser concluída; sem a pasta compartilhada de relatórios, a trava vale só neste
   computador e o painel avisa ([trava por caixa](../especificacoes/trava-por-caixa.md)).
   **Não espere a caixa inteira:** durante a análise, o cartão **Processos** mostra cada
   processo como *pronto*, *analisando* ou *na fila*; clique em **Conferir** no primeiro
   pronto. "Corrigir tudo", salvar o lote corrigido e o relatório da caixa esperam a
   análise terminar. Se a análise final achar algo novo num processo que você já
   conferiu (uma página duplicada de um processo que chegou depois, por exemplo), ele
   aparece na Sequência com a marca **reavaliar**, só com o achado novo; o que você já
   decidiu continua decidido.
   **Lote de demonstração:** "Analisar lote-demonstracao" abre um lote sintético já no
   servidor, com página faltando, em branco, torta e sem nitidez, sem enviar nada do
   aparelho. **Enviar lote:** no computador, arraste a pasta ou um `.zip`; no celular,
   escolha um `.zip` ou as imagens. Só documentos sintéticos ou públicos na PoC.
3. **Painel:** veredito, percentual que dispensa revisão, defeitos por severidade, por
   tipo e por estação.
4. **Revisão:** a fila mostra só o que foi sinalizado, do mais grave ao menos grave.
   A página aparece ampliada com a área do defeito destacada, a medida, o limiar e a
   correção proposta. Decida pelo teclado:

| Tecla | Ação |
| --- | --- |
| A | Aprovar: a sinalização era falso positivo |
| C | Aplicar a correção proposta (automática: gera uma cópia corrigida e reanalisa) |
| R | Reprovar: vai para a ordem de retrabalho |
| O | Defeito de origem: o papel já veio assim; não reprova o documento |
| ← → | Anterior / seguinte |
| Espaço | Ampliar a área do defeito / voltar |
| Ctrl+Z | Desfazer a última decisão |
| 1–4 | Mostrar só crítico, alto, médio ou baixo (de novo: todos) |
| N | Digitar a numeração correta da folha |
| Q / E | Girar a página 90° para a esquerda / direita, na cópia |
| W | Girar a página 180°, na cópia |

**Página de lado ou de cabeça para baixo:** com confiança alta, a rotação entra no
"Corrigir tudo"; com confiança média, aparece sugerida e você aplica com C. Em qualquer
página, Q, E e W (ou os botões **Girar a página**) giram a cópia; o giro é somado ao que
já está aplicado. Cada giro é uma decisão registrada com seu nome e horário e vai para o
lote corrigido; voltar à orientação original registra "não girar".

5. **Sequência:** miniaturas na ordem do arquivo com a numeração e o estado de cada
   página. Quando a numeração foi lida da imagem, o canto mostra o recorte exato onde ela
   foi procurada. **Ampliar**, duplo clique ou Z abre a página inteira, com
   Original/Corrigida, setas e Esc.
   - **Digitação rápida:** o cursor já começa na primeira página com dúvida. Digite o
     número e Enter: grava e vai para a próxima com dúvida. Tab passa sem gravar; Esc
     volta ao valor anterior. Pode digitar sem esperar: as gravações vão em fila. A
     etiqueta da página passa a dizer "digitado".
   - **Mudar a ordem:** arraste a página para o lugar certo ou use Alt + seta para a
     esquerda/direita na página (ou no campo do número). A faixa passa a se chamar
     "Ordem escolhida pelo revisor", com seu nome e horário, e essa ordem vale no lote
     corrigido ("movida da posição X para a Y pelo revisor"). **Voltar à ordem do
     arquivo** desfaz.
   - **Desfazer** (ou Ctrl+Z fora do campo) desfaz a última numeração ou mudança de
     ordem, uma de cada vez.
   - **Folha que apareceu depois:** escaneie só ela e arraste o arquivo do Windows para
     a faixa, no ponto onde deve entrar (a borda azul mostra o lado), ou solte em
     **Adicionar folha** (ou **Escolher arquivo…**) para ela entrar pelo número lido. A
     tela diz em que posição ela entrou; se não for aí, arraste para o lugar certo. A
     folha aparece como "folha inserida", com **Remover** para desfazer. A pasta
     original não é tocada: a folha fica na área de complementos do lote.
   - **Corrigir tudo** aplica as correções automáticas do documento (no painel e na
     revisão, **Corrigir o lote inteiro**). A tela de carregamento mostra quantas páginas
     já foram corrigidas. Depois aparecem as faixas **Antes** (como está no arquivo) e
     **Depois** (o lote corrigido, renumerado), com o que mudou em cada página.
   - Desfoque, resolução baixa e arquivo ilegível **não** são "melhorados": aparecem como
     "precisa redigitalizar" e vão para a ordem de retrabalho.
   - **Página faltando** aparece como um cartão no lugar da lacuna: decida *mandar para
     retrabalho*, *defeito de origem* ou *aprovar mesmo assim*. Enquanto houver página
     faltando sem decisão, **Salvar correções** fica bloqueado.
   - **Salvar correções** gera e baixa o lote corrigido; **Desfazer correções** desfaz só
     o que o "Corrigir tudo" aplicou. Até salvar, a tela avisa que as correções não
     foram salvas.
6. **Metadados:** confirme ou corrija os campos exigidos pelo Decreto 10.278/2020.
7. **Relatório:** salve o lote corrigido na pasta de saída (programa desktop) ou baixe o
   `.zip` (com aviso se ainda houver críticos pendentes),
   o relatório, os CSVs e a ordem de retrabalho por estação.
   - **Relatórios por caixa:** com todas as decisões da caixa tomadas, salvar gera o
     relatório da caixa (PDF para imprimir e JSON para a Gestão): páginas faltando e
     ilegíveis de cada processo, ou "Nenhuma pendência". O cartão mostra a versão mais
     nova de cada caixa e baixa o PDF. Se a pendência mudar depois, gere de novo: sai a
     versão 2 e a 1 fica guardada.

O original nunca é alterado: toda correção gera uma cópia, registrada com data, hora e
revisor.
