# Manual do conferente

Para quem nunca usou o programa. Você vai conferir a **caixa de exemplo** que vem no
pacote, do começo ao fim, em uns 15 minutos. Depois disso, uma caixa real é igual.

A conferência manual continua sendo a oficial durante o piloto: o programa aponta o
que achou, e quem decide é você. O original nunca é alterado; tudo o que você corrige
vai para uma cópia, o **lote corrigido**.

## Antes de começar

- Abra o `QA.exe` na pasta do programa. O seu nome no topo, à direita, é o usuário do
  Windows: é ele que fica registrado em cada decisão.
- A qualquer momento, aperte **?** para ver a lista de atalhos de teclado.
- A caixa de exemplo fica em `samples\lote-exemplo`, dentro da pasta do programa. Ela
  tem uma página torta, uma folha faltando, uma página em branco e uma sem nitidez.

## 1. Abrir a caixa

1. Na tela inicial, em **Abrir lote**, clique em **Escolher pasta…** e escolha
   `samples\lote-exemplo` (ou cole o caminho).
2. Deixe o perfil **sos-piloto** e clique em **Analisar lote**.
3. O painel mostra o progresso e o cartão **Processos**: cada processo aparece como
   *na fila*, *analisando* ou *pronto*. Não espere a caixa toda: clique em **Conferir**
   no primeiro pronto.

Se aparecer "Caixa … em conferência por …", outra pessoa está com a caixa em outra
máquina: combine com ela. **Assumir a caixa** só aparece se a outra máquina parou de
dar sinal há mais de 10 minutos.

## 2. Conferir a sequência das folhas

A tela **Sequência** mostra as páginas na ordem do arquivo, com o número da folha
embaixo de cada uma e o canto onde o número foi lido.

1. O cursor já está na primeira página com dúvida. Olhe o recorte do canto, digite o
   número e aperte **Enter**: o programa grava e pula para a próxima com dúvida.
   **Tab** passa sem gravar; **Esc** volta ao valor anterior.
2. Folha fora do lugar: arraste a página para o lugar certo (ou **Alt + ←/→**). A
   ordem que você escolher vai para o lote corrigido.
3. **Falta fls. 3** aparece num cartão vermelho no lugar da lacuna. Na caixa de
   exemplo, a folha não existe: escolha **Defeito de origem** (o papel já veio sem
   ela) ou **Mandar para retrabalho** (precisa localizar e redigitalizar).
4. Se a folha aparecer depois, escaneie só ela e arraste o arquivo para a sequência,
   no ponto certo, ou para **Adicionar folha**: ela entra pelo número lido e a lacuna
   fecha.
5. Errou? **Desfazer** (ou **Ctrl+Z** fora do campo) volta um passo.

## 3. Revisar as sinalizações

Na **Revisão**, a fila mostra uma sinalização por vez, da mais grave para a menos grave,
com a página e o motivo.

| Tecla | Quando usar |
| --- | --- |
| **C** | Aplicar a correção proposta (endireitar, girar, recortar borda, tirar página em branco) |
| **A** | O programa errou: aprovar como está (falso positivo) |
| **R** | Mandar para retrabalho (a página precisa ser redigitalizada) |
| **O** | Defeito de origem: o papel já veio assim |
| **Q / E / W** | Girar a página 90° para a esquerda, para a direita, ou 180° |
| **Espaço** | Ampliar a página |

Na caixa de exemplo:

- **Inclinação** (página torta): **C** endireita na cópia.
- **Página em branco:** **C** tira a página da cópia (folha com número nunca é tratada
  como branca).
- **Desfoque** (sem nitidez): não dá para melhorar sem inventar conteúdo: **R** manda
  redigitalizar.
- Qualquer outra sinalização em que você não vê problema na página: **A**.

O nome da sinalização aparece em destaque sobre a página. Quando a fila acaba, a tela
diz "Tudo decidido".

**Corrigir tudo** (na Sequência) aplica de uma vez as correções automáticas do
processo; ele só funciona depois que a caixa toda foi analisada.

## 4. Metadados

Em **Metadados**, confira os campos que o Decreto 10.278/2020 exige. Cada valor diz de
onde veio (do arquivo, do perfil, calculado). Corrija o que estiver errado e confirme.

## 5. Salvar e relatório da caixa

1. Em **Relatório**, clique em **Salvar na pasta de saída**. O lote corrigido vai para
   `Documentos\QA\Saída`, com a mesma estrutura de pastas, as páginas na ordem certa,
   os metadados e o hash de cada arquivo.
2. Com todas as decisões da caixa tomadas, sai o **relatório da caixa** (PDF para
   imprimir e arquivar): páginas faltando e ilegíveis de cada processo, ou "Nenhuma
   pendência". Ele substitui a folha de papel das pendências e aparece na **Gestão**.
3. Se uma pendência for resolvida depois (o retrabalho voltou, a folha apareceu), salve
   de novo: sai a versão 2 do relatório e a 1 fica guardada.

Pronto: a caixa de exemplo está conferida. Numa caixa real, o caminho é o mesmo.

## Se algo der errado

- **A tela mostra um erro:** tente de novo; se repetir, avise o suporte. O erro já fica
  registrado (sem conteúdo de documento) para o suporte ver no **Diagnóstico**.
- **"A pasta original mudou desde a análise":** alguém mexeu na pasta enquanto você
  conferia. Abra o lote de novo.
- **O programa fechou no meio:** abra de novo; as decisões estão salvas. A trava da
  caixa se solta sozinha em 10 minutos se o programa não voltar.

Mais detalhes de cada tela em [interface de revisão](interface.md).
