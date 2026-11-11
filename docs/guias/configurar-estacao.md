# Configurar uma estação de digitalização

O certo para uma Kodak i4250 não é necessariamente o certo para uma S2085f: o fundo do
vidro, o brilho do papel e a margem escura mudam de uma digitalizadora para outra. Por
isso os ajustes das regras podem ser dados no perfil inteiro e, por cima, em cada
estação.

No programa desktop, a aba **Digitalizadoras** da [tela de Configurações](../operacao/configuracoes.md)
mostra e muda esses ajustes, com a origem de cada valor.

## Ordem de aplicação

Para cada parâmetro de cada regra, vale o último que existir:

1. Padrão do `manifest.yaml` da regra (está na [referência de perfis](../referencia/perfis.md)).
2. `detectors.<regra>` do perfil.
3. `stations[].overrides.<regra>` da estação da página.

`enabled` segue a mesma ordem: o perfil liga ou desliga a regra, e a estação pode mudar
isso só para as páginas dela.

## Exemplo

```yaml
stations:
  - id: cg-e3
    make: Kodak
    model: i4250
    location: "Unidade Campo Grande, Estação 3"
    overrides:
      black_borders: { params: { dark_level: 60 } }
      exposure: { params: { reference_paper: 235 } }
  - id: centro-e1
    make: Kodak
    model: S2085f
    location: "Unidade Centro, Estação 1"
    overrides:
      duplicate_page: { enabled: false }
detectors:
  black_borders: { enabled: true }
  exposure: { enabled: true }
```

O perfil completo de exemplo é `profiles/sos-piloto.yaml`.

## Como a página é ligada à estação

1. Pelo fabricante, modelo e número de série gravados no arquivo (tags TIFF `Make`,
   `Model`), ou pela pasta do lote (`folder`), comparados com a tabela `stations`.
2. Se o arquivo não disser, vale a estação padrão deste computador
   (`default_station` em [Configurar este computador](configurar-computador.md)).
3. Sem nenhuma das duas, a página fica "não identificada" e usa só os ajustes do perfil.

A estação de cada página aparece no relatório (`station` e `station_id`) e na ordem de
retrabalho.

## Duplicatas entre estações

A comparação de duplicatas é feita entre pares de páginas. Cada par é julgado com os
parâmetros da página que seria a cópia (a menos nítida). Se a estação dessa página
desliga a regra, ela não entra na comparação.

## O resultado continua explicável

Cada lote analisado guarda uma cópia do perfil com que foi analisado. Mudar um limite
hoje não muda a explicação de um lote da semana passada.
