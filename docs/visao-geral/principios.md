# Princípios

Sete regras valem para qualquer decisão técnica. Quando uma funcionalidade conflita com
elas, a funcionalidade perde; uma regra só cai por [ADR](../adr/0000-template.md).

1. **Dado real não sai da empresa.** O motor em nuvem só recebe documentos sintéticos ou
   públicos, e apaga cada lote depois de 24 horas. Documento de cliente só é processado
   dentro da rede da empresa.
2. **O original é intocável.** O motor nunca altera o lote recebido. Toda correção gera
   um arquivo novo, com registro do que foi alterado
   ([correções](../especificacoes/corrections.md)).
3. **O humano decide.** A máquina sinaliza, pontua e sugere; aprovar, reprovar ou aplicar
   correção é sempre uma ação do revisor, registrada com nome, data e hora.
4. **Toda detecção explica a si mesma.** Cada sinalização mostra o motivo, a medida
   obtida, o limiar usado e, quando possível, a área da página destacada.
5. **Limiar é configuração, não código.** Cada cliente ou tipo de projeto tem um perfil
   com seus limiares e regras ([referência de perfis](../referencia/perfis.md)). Calibrar
   não exige recompilar.
6. **Contrato e especificação antes do código.** O comportamento é definido no contrato
   (ADR-0002) e nas [especificações](../especificacoes/index.md); o código implementa,
   não define. É isso que permite [trocar de linguagem](../guias/portar-linguagem.md)
   sem mudar o sistema.
7. **Sem documentação, não está pronto.** Toda regra, decisão e interface é documentada
   nesta pasta, e a integração contínua cobra isso (ADR-0017).
