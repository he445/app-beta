<!-- Gerado por tools/docs/gen_reference.py. Não edite: mude a fonte e gere de novo. -->

# Referência de perfis

Um perfil é um arquivo YAML em `profiles/`, validado contra
`contracts/schemas/profile.schema.json`. Ele diz quais regras ligam, com quais
limiares, e como a numeração e as estações são tratadas.

## Campos

| Campo | Tipo | Obrigatório | Padrão | Descrição |
| --- | --- | --- | --- | --- |
| `id` | texto | sim |  | padrão `^[a-z0-9_-]+$` |
| `name` | texto | sim |  |  |
| `organization` | texto | sim |  | Pessoa jurídica responsável pela digitalização. |
| `resolution` | objeto |  |  |  |
| `resolution.min_dpi` | número |  |  | mín. 1 |
| `verdict` | objeto |  |  |  |
| `verdict.max_yellow_ratio` | número |  |  | mín. 0, máx. 1 |
| `verdict.green_sample_ratio` | número |  |  | mín. 0, máx. 1 |
| `numbering` | objeto |  |  |  |
| `numbering.enabled` | sim/não |  |  |  |
| `numbering.mode` | `simple` ou `recto_verso` |  |  |  |
| `numbering.min_confidence` | número |  |  | mín. 0, máx. 1 |
| `numbering.high_confidence` | número |  |  | mín. 0, máx. 1 |
| `identifier_pattern` | texto |  |  | Campos: {batch}, {document}, {seq}. |
| `stations` | lista de objeto |  |  |  |
| `stations[].location` | texto | sim |  |  |
| `stations[].make` | texto |  |  |  |
| `stations[].model` | texto |  |  |  |
| `stations[].serial` | texto |  |  |  |
| `stations[].folder` | texto |  |  |  |
| `detectors` | objeto |  |  |  |

## Regras e parâmetros

Cada regra aceita `enabled`, `severity` e `params` em `detectors.<regra>`. Os padrões
abaixo vêm do `manifest.yaml` de cada regra; o perfil só precisa citar o que muda.

### `corrupted_file`

Arquivo corrompido. Versão 1.0.0, severidade `critical`.
Especificação: [corrupted_file.md](../especificacoes/detectors/corrupted_file.md).

Sem parâmetros.

### `low_resolution`

Resolução abaixo do exigido. Versão 1.0.0, severidade `high`.
Especificação: [low_resolution.md](../especificacoes/detectors/low_resolution.md).

| Parâmetro | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `min_dpi` | número | `300` | mín. 1 | Resolução mínima exigida pelo perfil (Anexo I do Decreto 10.278/2020) |

### `blank_page`

Página em branco. Versão 1.0.0, severidade `low`.
Especificação: [blank_page.md](../especificacoes/detectors/blank_page.md).

| Parâmetro | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `blank_threshold` | número | `0.003` | mín. 0, máx. 1 | Cobertura abaixo da qual a página é branca |
| `near_blank_threshold` | número | `0.01` | mín. 0, máx. 1 | Cobertura abaixo da qual a página é quase branca |
| `mark_min_area` | inteiro | `400` | mín. 0 | Área em pixels a 150 dpi de uma marca isolada (carimbo, rubrica) que impede classificar como branca |
| `remove_blank_pages` | sim/não | `true` |  | Se a correção proposta para página branca é removê-la |

### `black_borders`

Bordas pretas. Versão 1.0.0, severidade `low`.
Especificação: [black_borders.md](../especificacoes/detectors/black_borders.md).

| Parâmetro | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `min_fraction` | número | `0.01` | mín. 0, máx. 1 | Largura mínima da faixa, como fração da dimensão da página |
| `dark_level` | inteiro | `70` | mín. 0, máx. 255 | Nível de cinza abaixo do qual o pixel é escuro |
| `dark_fraction` | número | `0.9` | mín. 0, máx. 1 | Fração de pixels escuros para a linha ou coluna contar como faixa |

### `blur`

Desfoque. Versão 1.0.0, severidade `critical`.
Especificação: [blur.md](../especificacoes/detectors/blur.md).

| Parâmetro | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `relative_threshold` | número | `0.4` | mín. 0, máx. 1 | Fração da mediana do lote abaixo da qual a página é sinalizada |
| `absolute_threshold` | número | `0.6` | mín. 0 | Limiar usado quando o lote tem menos de min_batch_size páginas elegíveis |
| `min_batch_size` | inteiro | `5` | mín. 1 | Páginas elegíveis necessárias para usar a mediana do lote |
| `min_ink_coverage` | número | `0.005` | mín. 0, máx. 1 | Cobertura de tinta mínima para a página ser avaliada |

### `skew`

Inclinação. Versão 1.0.0, severidade `medium`.
Especificação: [skew.md](../especificacoes/detectors/skew.md).

| Parâmetro | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `flag_threshold` | número | `0.5` | mín. 0 | Ângulo absoluto, em graus, acima do qual a página é sinalizada |
| `reject_threshold` | número | `3.0` | mín. 0 | Ângulo absoluto acima do qual a severidade sobe para alto |
| `max_angle` | número | `10.0` | mín. 1, máx. 45 | Faixa de busca, em graus, para cada lado |
| `min_ink_coverage` | número | `0.005` | mín. 0, máx. 1 | Cobertura mínima para estimar o ângulo |

### `exposure`

Escura, clara ou sem contraste. Versão 1.0.0, severidade `high`.
Especificação: [exposure.md](../especificacoes/detectors/exposure.md).

| Parâmetro | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `z_threshold` | número | `2.0` | mín. 0 | Desvios robustos da mediana do lote para sinalizar |
| `min_batch_size` | inteiro | `5` | mín. 1 | Páginas elegíveis necessárias para usar a mediana do lote |
| `min_ink_pixels` | inteiro | `500` | mín. 1 | Pixels de tinta mínimos para medir contraste |
| `min_sigma_paper` | número | `8.0` | mín. 0.1 | Piso do desvio do brilho do papel, em níveis de cinza |
| `min_sigma_contrast` | número | `15.0` | mín. 0.1 | Piso do desvio do contraste, em níveis de cinza |
| `reference_paper` | número | `240.0` | mín. 0, máx. 255 | Brilho de papel de referência para lote pequeno |
| `reference_contrast` | número | `190.0` | mín. 0, máx. 255 | Contraste de referência para lote pequeno |

### `duplicate_page`

Página duplicada. Versão 1.0.0, severidade `medium`.
Especificação: [duplicate_page.md](../especificacoes/detectors/duplicate_page.md).

| Parâmetro | Tipo | Padrão | Faixa | Descrição |
| --- | --- | --- | --- | --- |
| `max_hash_distance` | inteiro | `48` | mín. 0, máx. 256 | Distância de Hamming máxima entre dHash de 256 bits para virar candidato |
| `min_similarity` | número | `0.95` | mín. 0, máx. 1 | Correlação mínima das miniaturas para confirmar a duplicata |
| `min_ink_coverage` | número | `0.005` | mín. 0, máx. 1 | Páginas com menos tinta (brancas) não são comparadas |

### `missing_page`

Página faltando. Versão 1.1.0, severidade `critical`.
Especificação: [sequencing.md](../especificacoes/sequencing.md).

Sem parâmetros.

### `out_of_order`

Página fora de ordem. Versão 1.1.0, severidade `medium`.
Especificação: [sequencing.md](../especificacoes/sequencing.md).

Sem parâmetros.

### `numbering_review`

Revisar numeração. Versão 1.1.0, severidade `high`.
Especificação: [sequencing.md](../especificacoes/sequencing.md).

Sem parâmetros.

### `completeness_unverifiable`

Completude não verificável. Versão 1.1.0, severidade `low`.
Especificação: [sequencing.md](../especificacoes/sequencing.md).

Sem parâmetros.
