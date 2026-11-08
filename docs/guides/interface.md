# Interface de revisão

Guia para garantidores e conferentes. Para instalar e publicar, veja
[`ui/README.md`](https://github.com/he445/prova-de-conceito/blob/main/ui/README.md).

## Fluxo

1. **Entrar** com seu nome (vai em cada decisão) e o token de acesso.
2. **Enviar lote:** arraste a pasta ou um `.zip`, escolha o perfil e, se houver, o
   manifesto com a contagem declarada. Só documentos sintéticos ou públicos na PoC.
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

5. **Sequência:** miniaturas na ordem do arquivo com a numeração lida e o canto ampliado.
   Clique numa página (ou Enter) para corrigir a numeração; duplo clique (ou Z) abre a
   página ampliada, com Original/Corrigida, setas e Esc.
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
7. **Relatório:** baixe o lote corrigido (com aviso se ainda houver críticos pendentes),
   o relatório, os CSVs e a ordem de retrabalho por estação.

O original nunca é alterado: toda correção gera uma cópia, registrada com data, hora e
revisor.
