# Interface de revisão

Referência das telas para garantidores e conferentes; para começar, leia o
[manual do conferente](manual-do-conferente.md). Dentro do programa, a tecla **?**
mostra todos os atalhos. Para instalar e publicar, veja
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
   pronto. **Corrigir pasta**, **Corrigir tudo** e **Decidir semelhantes** já valem para
   os processos prontos; salvar o lote corrigido e o relatório da caixa esperam a
   análise terminar. Se a análise final achar algo novo num processo que você já
   conferiu (uma página duplicada de um processo que chegou depois, por exemplo), ele
   aparece na Sequência com a marca **reavaliar**, só com o achado novo; o que você já
   decidiu continua decidido.
   **Lote de demonstração:** "Analisar lote-demonstracao" abre um lote sintético já no
   servidor, com página faltando, em branco, torta e sem nitidez, sem enviar nada do
   aparelho. **Enviar lote:** no computador, arraste a pasta ou um `.zip`; no celular,
   escolha um `.zip` ou as imagens. Só documentos sintéticos ou públicos na PoC.
3. **Painel:** veredito, percentual que dispensa revisão, defeitos por severidade, por
   tipo e por estação. **Salvar caixa** grava a versão corrigida da caixa (na pasta de
   saída no programa desktop, senão baixa o `.zip`) e gera o relatório das caixas
   concluídas; fica bloqueado, com o motivo ao lado, enquanto houver página faltando sem
   decisão ou correção em andamento. **Aprovar tudo (defeito de origem)** aceita a caixa
   como está: toda sinalização sem decisão vira defeito de origem, com uma ressalva
   opcional que vale para todas e sai no relatório para o cliente. Nada vai para
   retrabalho e o veredito fica "aprovado com ressalvas". Antes de gravar, o painel
   mostra quantas sinalizações entram e de que tipo. Página faltando tem **alerta
   próprio**: a lista de cada pasta com as folhas que faltam. **Confirmar, com as páginas
   faltando** marca também essas como defeito de origem (o papel já veio sem a folha) e o
   relatório da caixa lista a pasta e as folhas; **Só as outras** deixa as páginas
   faltando para decidir uma a uma no cartão da Sequência. O andamento aparece no
   painel e **Desfazer** desfaz a operação inteira de uma vez.
4. **Revisão:** a revisão anda **pasta por pasta**. Ela abre na primeira pasta com
   pendência; o seletor **Pasta** no topo da fila mostra cada pasta com quantas faltam
   (ou "concluída") e **Próxima pasta →** pula para a seguinte com pendência. O nome da
   pasta fica no alto da tela e o progresso conta só a pasta (a caixa aparece embaixo).
   Ao terminar uma pasta, a tela oferece ir para a próxima; "Todas as pastas" volta à
   fila única da caixa. Dentro da pasta, a fila mostra só o que foi sinalizado, do mais
   grave ao menos grave. A página aparece ampliada com a área do defeito destacada, a medida, o limiar e a
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

**Em lote, na própria revisão:** no topo da fila, **Corrigir pasta** aplica o automático
da pasta da sinalização que está na tela e **Corrigir tudo**, o de todas as pastas. No
painel da sinalização, **Decidir semelhantes** aplica a mesma decisão (aprovar,
retrabalho ou defeito de origem) em todas as pendentes da mesma categoria, só **nesta
pasta** ou **na caixa**. Por exemplo, aprovar de uma vez toda "Resolução abaixo do
exigido" de uma caixa digitalizada sem DPI gravado. O programa pede confirmação dizendo
quantas serão decididas, e **Desfazer** volta tudo de uma vez. Página faltando não entra:
decida cada uma.

5. **Sequência:** miniaturas na ordem do arquivo com a numeração e o estado de cada
   página. Quando a numeração foi lida da imagem, o canto mostra o recorte exato onde ela
   foi procurada. **Ampliar**, duplo clique ou Z abre a página inteira, com
   Original/Corrigida, setas e Esc. Na página ampliada, **Aprovar** (ou A) aprova como
   falso positivo as sinalizações pendentes daquela página e passa para a seguinte; o
   botão mostra quantas faltam e diz "Sem pendência" quando não há. **Defeito de
   origem** (ou O) abre um campo para a ressalva (opcional, por exemplo "original
   manchado"): Enter confirma, marca as pendentes da página como defeito de origem com
   essa ressalva e passa para a seguinte; Esc desiste.
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
   - **Corrigir pasta** aplica as correções automáticas só da pasta (na Sequência e na
     revisão); **Corrigir tudo** aplica as de todas as pastas da caixa (no painel e na
     revisão). Com a caixa ainda em análise, o botão diz "Corrigir tudo (pastas
     prontas)": rode de novo quando a análise terminar. A tela de carregamento mostra quantas páginas
     já foram corrigidas. Depois aparecem as faixas **Antes** (como está no arquivo) e
     **Depois** (o lote corrigido, renumerado), com o que mudou em cada página.
   - Desfoque, resolução baixa e arquivo ilegível **não** são "melhorados": aparecem como
     "precisa redigitalizar" e vão para a ordem de retrabalho.
   - **Página faltando** aparece como um cartão no lugar da lacuna: decida *mandar para
     retrabalho*, *defeito de origem* ou *aprovar mesmo assim*. Enquanto houver página
     faltando sem decisão, **Salvar correções** fica bloqueado.
   - **Salvar correções** gera e baixa o lote corrigido; **Desfazer correções** desfaz só
     o que o "Corrigir pasta" ou o "Corrigir tudo" aplicou. Até salvar, a tela avisa que as correções não
     foram salvas.
6. **Metadados:** confirme ou corrija os campos exigidos pelo Decreto 10.278/2020.
7. **Relatório:** salve o lote corrigido na pasta de saída (programa desktop) ou baixe o
   `.zip` (com aviso se ainda houver críticos pendentes),
   o relatório, os CSVs e a ordem de retrabalho por estação.
   - **Relatórios por caixa:** com todas as decisões médio ou acima da caixa tomadas
     (as baixas não seguram), salvar gera o
     relatório da caixa (PDF para imprimir e JSON para a Gestão): páginas faltando,
     páginas ilegíveis (arquivo corrompido) e defeitos de imagem por tipo (desfocadas,
     exposição ruim, resolução abaixo do exigido) de cada processo, ou "Nenhuma
     pendência". O cartão mostra a versão mais
     nova de cada caixa e baixa o PDF; caixa ainda não concluída aparece com o que falta
     decidir.
   - **Defeitos de origem (para o cliente):** as páginas faltando aceitas aparecem à
     parte, com a pasta e as folhas ("CX1/proc-7: fls. 13 e 14"); os outros itens trazem
     a pasta, o defeito e a ressalva do revisor. Se a pendência mudar depois, gere de novo: sai a
     versão 2 e a 1 fica guardada.

O original nunca é alterado: toda correção gera uma cópia, registrada com data, hora e
revisor.
