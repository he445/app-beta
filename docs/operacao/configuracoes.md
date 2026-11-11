# Tela de Configurações

No programa desktop, **Configurações** (no topo, à direita) tem duas abas. Cada valor
mostra de onde veio, e um valor inválido é recusado antes de salvar, com o motivo ao
lado do campo.

## Digitalizadoras

Ajustes das regras por perfil e por estação ([como os valores se combinam](../guias/configurar-estacao.md)).

1. Escolha o perfil e, em **Ajustar para**, o perfil inteiro ou uma estação.
2. Cada regra mostra se está ligada e cada parâmetro mostra o valor, a origem
   (padrão da regra, perfil ou estação) e o padrão da regra.
3. Mude os valores e clique em **Salvar mudanças**. Fora da faixa permitida, o campo
   fica marcado e o botão não salva.
4. **Voltar ao herdado** tira o ajuste daquele nível: o valor volta a vir do perfil ou do
   padrão da regra.

A mudança grava no perfil. Lotes já analisados continuam explicados pelo perfil com que
foram analisados.

## Este computador

Pastas, estação padrão, recursos e log ([referência](../referencia/configuracao.md)).
O que você salvar fica no seu arquivo de configuração e vale na **próxima abertura** do
programa. O que a TI travou aparece só para leitura ("travado pela TI"). Se uma variável
`QA_*` ou um argumento estiver sobrepondo um valor nesta abertura, a tela avisa.
