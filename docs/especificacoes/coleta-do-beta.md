# Coleta do beta e métricas do piloto

O que o programa guarda das confirmações dos garantidores e como `qa beta report`
calcula as métricas que a coordenação acompanha. Tudo fica nesta máquina: nada é
enviado para fora, nem por rede nem por telemetria.

## Exemplos rotulados

Ligados pelo perfil (`feedback.enabled`; no perfil do piloto, ligado) e guardados no
banco do programa, com as imagens em `data_dir/feedback/`. Um exemplo por tipo e
página: uma nova confirmação da mesma página substitui a anterior, e desfazer a
confirmação apaga o exemplo.

| Tipo | Quando | Rótulo (o revisor) | Modelo | Imagem |
| --- | --- | --- | --- | --- |
| `numbering` | O revisor digita a numeração na tela de Sequência ou na revisão | número digitado | valor e estado resolvidos, origem e marcas lidas | recorte da região da numeração (só quando lida da imagem) |
| `orientation` | O revisor decide uma sinalização de orientação ou gira a página | giro mantido (0 quando aprovou sem girar) | ângulo proposto (`null` quando o modelo não sinalizou) e confiança | miniatura da página (256 px de largura) |

Decisões tomadas pelo "Corrigir tudo" não viram exemplo: não são confirmação de uma
pessoa. Cada exemplo vence em `feedback.retention_days` (padrão 180) e é apagado,
com a imagem, na limpeza periódica do programa.

`qa feedback export --out pacote.zip` grava `numeracao/labels.json` (no formato do
`tools/bench_numbering.py`: `file`, `text`, `struck`, mais `model`) e
`orientacao/labels.json` (`file`, `angle_deg`, `model_angle_deg`, `confidence`), com as
imagens e um `LEIA-ME.txt` sobre o cuidado com dado pessoal.

## Métricas (`qa beta report`)

Calculadas dos lotes do período (pela data de criação do lote). As contagens de cada
lote são guardadas antes de a retenção apagar o lote, então o relatório cobre o beta
inteiro; elas têm só números, nenhum conteúdo de documento.

| Métrica | Definição |
| --- | --- |
| Alertas do programa decididos | Sinalizações do programa com decisão; criadas pelo revisor não contam |
| Problema de verdade | Decididas como corrigir, retrabalho ou defeito de origem |
| Falso positivo | Aprovadas ("falso positivo" na revisão) |
| Precisão | problema de verdade ÷ (problema de verdade + falso positivo) |
| Achados só pelo garantidor | Páginas que o revisor girou sem sinalização do modelo, mais numerações lidas com segurança (estado `read`) que o revisor corrigiu |
| Cobertura estimada | problema de verdade ÷ (problema de verdade + achados só pelo garantidor) |
| Rotações mantidas | Sinalizações de orientação do modelo decididas com o mesmo ângulo proposto |
| Rotações automáticas desfeitas | Da faixa automática, decididas com outro ângulo ou sem girar (meta: zero; cada uma sobe `auto_threshold`) |
| Numeração bateu | Páginas com numeração menos as digitadas com valor diferente do que o modelo tinha resolvido |
| Precisaram de digitação | Páginas com numeração digitada |
| Sem precisar de revisão | `pages_without_review` do resumo de cada lote |
| Tempo de análise | Da criação do lote até o fim da análise |
| Tempo de revisão | Da primeira à última decisão ou digitação do lote |
| Originais | Lotes locais conferidos contra o retrato tirado na abertura; meta: nenhum alterado |

O tempo do processo atual não está no banco: a comparação é feita pela coordenação com
o tempo medido da conferência manual.
