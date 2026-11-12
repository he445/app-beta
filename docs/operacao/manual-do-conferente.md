# Manual do conferente

Para quem confere caixas digitalizadas e nunca usou o programa. Leia uma vez do começo
ao fim e confira a **caixa de exemplo** que vem com o programa; depois disso, uma caixa de
verdade é igual.

## O que o programa faz

Ele olha cada página da caixa e aponta o que pode estar errado: página torta, de lado,
em branco, escura, sem nitidez, duplicada, com borda preta, com resolução baixa, folha
faltando ou fora de ordem. **Quem decide é você.** O programa propõe; você aprova,
manda corrigir ou manda para retrabalho. Cada decisão fica registrada com o seu nome
(o usuário do Windows) e o horário.

A pasta original nunca é alterada. As correções vão para uma cópia, o **lote corrigido**,
gravado em `Documentos\QA\Saída`.

## Antes de começar

- Abra o **QA.exe**. Não há senha: o programa usa o seu usuário do Windows.
- Saiba onde está a pasta da caixa: no computador (`D:\Lotes\0412`) ou na rede
  (`\\servidor\digitalizacao\0412`).
- Aperte **?** em qualquer tela para ver todos os atalhos de teclado. **Esc** fecha.

## Conferir uma caixa, passo a passo

### 1. Abrir a caixa

Na tela inicial, no cartão **Abrir lote**:

1. Cole o caminho da pasta em **Pasta do lote** (ou clique em **Escolher pasta…**).
2. Deixe o perfil que já vem escolhido.
3. Clique em **Analisar lote**.

O programa espera a pasta parar de mudar (se a digitalizadora ainda estiver gravando) e
analisa. Não precisa esperar a caixa inteira: no cartão **Processos**, o primeiro processo
que aparecer como *pronto* já pode ser conferido em **Conferir**.

Se aparecer **"Caixa … em conferência por …, na máquina …, desde …"**, outra pessoa está
com essa caixa. Não abra: escolha outra caixa ou fale com ela. Se a mensagem disser que
a trava **foi abandonada** (a outra máquina parou de dar sinal há mais de dez minutos),
aparece **Assumir a caixa**: só clique se tiver certeza de que ninguém está nela.

### 2. Olhar o painel

Quando a análise termina, o **Painel** mostra o veredito, quantas páginas dispensam
revisão e o que foi encontrado. Clique em **Revisar N pendente(s)**.

### 3. Decidir cada sinalização (Revisão)

A tela mostra uma sinalização por vez, da mais grave para a menos grave: a página
ampliada com a área do problema marcada, o que foi medido e a correção proposta. Decida
com uma tecla; a próxima aparece sozinha.

| Tecla | Quando usar |
| --- | --- |
| **C** Corrigir | A correção proposta resolve: endireitar, girar, recortar borda, tirar página em branco ou duplicada. A cópia é corrigida na hora |
| **R** Retrabalho | A página precisa ser digitalizada de novo (sem nitidez, resolução baixa, arquivo que não abre) ou a folha precisa ser procurada (página faltando) |
| **A** Aprovar | O programa se enganou: a página está boa |
| **O** Defeito de origem | O papel já veio assim (rasgado, manchado, faltando no processo físico); não é culpa da digitalização |

Outras teclas úteis: **← →** anterior e seguinte, **Espaço** amplia, **Ctrl+Z** desfaz a
última decisão, **Q E W** giram a página, **N** digita o número da folha.

No alto da fila, **"X de Y decididas"** mostra quanto falta. Quando chega a Y de Y, a
tela diz **Fila vazia**.

### 4. Conferir a sequência (quando houver dúvida de numeração)

Em **Sequência**, cada miniatura mostra o número da folha lido e o estado. Onde o
programa não leu com segurança, o cursor já está no campo do número: digite e aperte
**Enter**. **Tab** passa sem gravar. Para mudar a ordem, arraste a página ou use
**Alt + ← →**. **Página faltando** aparece como um cartão no lugar da folha: decida ali
mesmo (retrabalho, defeito de origem ou aprovar).

Se a folha que faltava aparecer, escaneie só ela e arraste o arquivo para a sequência,
no lugar certo (veja [Interface de revisão](interface.md)).

### 5. Salvar e imprimir o relatório da caixa

Em **Relatório**:

1. Clique em **Salvar na pasta de saída**. A tela mostra **Gravado em …** com a pasta do
   lote corrigido.
2. O cartão **Relatórios por caixa** mostra a caixa com quantas folhas faltam e quantas
   páginas estão ilegíveis. Abra o **PDF** para imprimir ou arquivar: ele substitui a
   folha de papel das pendências.

Pronto: a caixa está conferida. Se uma pendência for resolvida depois, salve de novo: sai
a versão 2 do relatório e a 1 fica guardada.

## Treinar com a caixa de exemplo

O programa vem com uma caixa de treino em `samples\lote-exemplo`, dentro da pasta do
programa. Abra essa pasta no passo 1 e siga os passos. O que você deve encontrar:

| Sinalização | Onde | O que fazer |
| --- | --- | --- |
| Página faltando | Processo `DOC0001`: falta a folha 3 | **R** (retrabalho: procurar a folha) |
| Inclinação | `DOC0001`, segunda página, torta 3° | **C** (o programa endireita a cópia) |
| Página em branco | `DOC0001`, quarta página | **C** (sai do lote corrigido) |
| Desfoque | `DOC0002`, segunda página | **R** (digitalizar de novo) |
| Escura, clara ou sem contraste | Uma das páginas | Olhe a página: dá para ler? **A** (aprovar) |

Ao salvar, o relatório da caixa **CX001** deve mostrar **1 folha faltando** (fls. 3, em
`DOC0001`) e **1 página ilegível** (em `DOC0002`). Se o seu resultado for esse, você já
sabe conferir uma caixa.

## Situações comuns

- **"Reavaliar" num processo que você já conferiu:** a análise final da caixa achou algo
  novo nele (uma página duplicada de outro processo, por exemplo). Decida só o achado
  novo; o resto continua decidido.
- **Página ilegível × número ilegível:** página ilegível é a que precisa ser
  digitalizada de novo. Se só o número da folha não dá para ler mas a página está boa,
  digite o número na Sequência; isso não é pendência da caixa.
- **Faixa "A trava da caixa vale só neste computador"** no painel: a pasta compartilhada
  da rede não está configurada ou está fora do ar. Avise a TI; você pode continuar.
- **Faixa "A caixa … foi assumida por …"**: outra pessoa assumiu essa caixa noutra
  máquina. Pare e combine com ela quem termina.
- **Errou uma decisão:** **Ctrl+Z** na Revisão, ou volte à sinalização e decida de novo.

## Quando pedir ajuda

Se aparecer uma mensagem de erro ou o programa não abrir, anote o que estava fazendo e
avise o suporte. Os erros ficam registrados automaticamente (sem imagens nem texto dos
documentos) e o suporte os vê na tela de [Diagnóstico](diagnostico.md).

Para os termos (folha, processo, caixa, renumeração), veja o [glossário](../glossario.md).
