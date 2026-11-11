# Configurar este computador

A configuração do computador diz **onde** o programa guarda as coisas e **quanto** da
máquina ele pode usar. O padrão de qualidade (quais regras ligam e com quais limites)
não fica aqui: fica no [perfil](../referencia/perfis.md).

Todas as chaves, com tipo, padrão e variável de ambiente, estão na
[referência de configuração](../referencia/configuracao.md).

No programa desktop, a aba **Este computador** da [tela de Configurações](../operacao/configuracoes.md)
grava o arquivo do usuário, com a mesma validação.

## Camadas

Cada camada sobrescreve a anterior:

| # | Camada | Onde fica | Quem mexe |
| --- | --- | --- | --- |
| 1 | Padrões embutidos | No programa | Ninguém |
| 2 | Arquivo da máquina | `%PROGRAMDATA%\SOSDocs\QA\config.toml` | TI, se quiser |
| 3 | Arquivo do usuário | `%LOCALAPPDATA%\SOSDocs\QA\config.toml` | O próprio usuário |
| 4 | Variáveis `QA_*` | Ambiente do processo | Suporte, servidor, contêiner |
| 5 | Argumentos `--set chave=valor` | Linha de comando | Suporte e testes |

O motor em servidor (contêiner, nuvem) usa só as camadas 1 e 4: as mesmas variáveis
`QA_*` de sempre. Fora do Windows os arquivos ficam nas pastas equivalentes do sistema
(`platformdirs`).

## Formato do arquivo

TOML, com as chaves no primeiro nível:

```toml
workers = 3
output_dir = 'D:\QA\Saída'
allowed_roots = ['\\servidor\digitalizacao', 'D:\Lotes']
batch_settle_seconds = 30
log_level = "info"
```

Use aspas simples em caminhos do Windows: nelas a barra invertida não precisa ser
dobrada.

## Travar chaves

Só o arquivo da máquina pode travar chaves. Uma chave travada não é mudada por nenhuma
camada seguinte (arquivo do usuário, variável ou argumento), e a tela de Configurações a
mostra como somente leitura:

```toml
allowed_roots = ['\\servidor\digitalizacao']

[locked]
keys = ["allowed_roots"]
```

Travar uma chave sem dar valor a ela no arquivo da máquina fixa o padrão embutido.

## Quando a configuração está errada

Configuração inválida nunca é ignorada em silêncio. O programa para e diz a chave, a
origem e o que era esperado:

```text
workers em C:\Users\maria\AppData\Local\SOSDocs\QA\config.toml: esperado "auto" ou número inteiro ≥ 1 ≤ 256; veio 0
```

Chave desconhecida (erro de digitação, por exemplo) também é erro, com a lista das chaves
válidas.

## Recursos do computador

- `workers = "auto"` usa os núcleos da máquina menos um, no mínimo um.
- `max_memory_mb = "auto"` usa metade da memória do computador como teto. O motor estima
  400 MB por processo de análise e reduz o número de processos para caber no teto.
