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

5. **Sequência:** miniaturas na ordem do arquivo com a numeração lida, o canto ampliado,
   lacunas em vermelho e a ordem proposta. Clique numa página para corrigir a numeração.
6. **Metadados:** confirme ou corrija os campos exigidos pelo Decreto 10.278/2020.
7. **Relatório:** exporte o relatório, os CSVs e a ordem de retrabalho por estação.

O original nunca é alterado: toda correção gera uma cópia, registrada com data, hora e
revisor.
