<!-- Gerado por tools/docs/gen_reference.py. Não edite: mude a fonte e gere de novo. -->

# Referência de configuração

Configuração deste computador: pastas, recursos e acesso. Descreve a máquina, não o padrão de qualidade (esse fica no perfil). Cada camada (arquivo da máquina, arquivo do usuário, variáveis QA_*, argumentos) é validada contra este esquema.

A fonte é `contracts/schemas/settings.schema.json`. Como as camadas se combinam e
onde fica cada arquivo: [Configurar este computador](../guias/configurar-computador.md).

| Chave | Tipo | Obrigatório | Padrão | Descrição |
| --- | --- | --- | --- | --- |
| `workers` | `auto` ou inteiro |  | `"auto"` | Quantos processos analisam ao mesmo tempo. `auto` = núcleos − 1, mínimo 1. Variável: QA_WORKERS. |
| `max_memory_mb` | `auto` ou inteiro |  | `"auto"` | Teto de memória da análise, em MB; o motor reduz o paralelismo para caber nele. `auto` = metade da memória do computador. Variável: QA_MAX_MEMORY_MB. |
| `data_dir` | texto |  |  | Banco SQLite, miniaturas, cópias corrigidas e log. Padrão: `%LOCALAPPDATA%\SOSDocs\QA` no desktop; `./data` no servidor. Variável: QA_DATA_DIR. |
| `output_dir` | texto ou vazio |  |  | Onde vai o lote corrigido gravado em pasta. Padrão: `Documentos\QA\Saída` no desktop; `saida` dentro de `data_dir` no servidor. Variável: QA_OUTPUT_DIR. Vazio = o padrão calculado. |
| `temp_dir` | texto ou vazio |  |  | Arquivos temporários de correção. Padrão: `tmp` dentro de `data_dir`. Variável: QA_TEMP_DIR. Vazio = o padrão calculado. |
| `allowed_roots` | lista de texto |  | `[]` | Pastas e compartilhamentos de rede de onde se pode abrir lote. Vazio = qualquer pasta que o usuário consiga ler. Variável: QA_ALLOWED_ROOTS (separadas por `;`). |
| `default_station` | texto ou vazio |  |  | Identificador da estação usada quando o arquivo não diz de qual digitalizadora veio. Variável: QA_DEFAULT_STATION. padrão `^[a-z0-9_-]+$` |
| `batch_settle_seconds` | número |  |  | Espera o lote ficar esse tempo sem nenhum arquivo mudar antes de analisar (a digitalizadora pode ainda estar gravando). Padrão: 30 no desktop; 0 no servidor. Variável: QA_BATCH_SETTLE_SECONDS. mín. 0, máx. 3600 |
| `retention_days` | número |  |  | Quanto tempo ficam guardados os lotes enviados, as miniaturas e as cópias corrigidas. Padrão: 30 no desktop; 1 no servidor. Variáveis: QA_RETENTION_DAYS ou QA_RETENTION_HOURS. |
| `log_level` | `debug` ou `info` ou `warning` ou `error` |  | `"info"` | Detalhe do log. Variável: QA_LOG_LEVEL. |
| `profiles_dir` | texto |  |  | Pasta dos perfis YAML. Padrão: `profiles` ao lado do programa. Variável: QA_PROFILES_DIR. |
| `ui_dir` | texto ou vazio |  |  | Interface compilada para servir na mesma origem. Variável: QA_UI_DIR. |
| `demo_dir` | texto ou vazio |  |  | Lotes de demonstração, uma subpasta por lote. Variável: QA_DEMO_DIR. |
| `models_dir` | texto ou vazio |  |  | Pasta dos modelos embarcados, com models.lock.json ao lado. Padrão: models ao lado do programa no desktop; vazio no servidor (sem modelos). Variável: QA_MODELS_DIR. |
| `max_upload_mb` | inteiro |  | `2048` | Limite do envio de lote pelo navegador, em MB. Variável: QA_MAX_UPLOAD_MB. mín. 1 |
| `cors_origins` | lista de texto |  | `[]` | Origens de interface publicada noutro endereço. Vazio = nenhuma (interface na mesma origem). Variável: QA_CORS_ORIGINS (separadas por vírgula). |
| `api_token` | texto ou vazio |  |  | Token exigido em `Authorization: Bearer`. Vazio desliga a autenticação (só desenvolvimento e demonstração com dados sintéticos). No desktop é gerado a cada abertura e não é lido de arquivo. Variável: QA_API_TOKEN. |
| `diagnostics_dir` | texto ou vazio |  |  | Pasta compartilhada da rede onde cada computador grava seus erros, para ver todas as máquinas num lugar só. Vazio = só neste computador. Variável: QA_DIAGNOSTICS_DIR. |
| `reports_dir` | texto ou vazio |  |  | Pasta compartilhada da rede onde cada caixa concluída grava o relatório (JSON e PDF), lida pela tela de Gestão de qualquer computador. Vazio = só na pasta de saída deste computador. Variável: QA_REPORTS_DIR. |
| `admin_token_hash` | texto ou vazio |  |  | Hash (scrypt) do token de administrador, gravado por `qa admin token`. Só vale no arquivo da máquina. Vazio = área de administração desligada. padrão `^scrypt\$\d+\$\d+\$\d+\$[A-Za-z0-9_=-]+\$[A-Za-z0-9_=-]+$` |
| `locked` | objeto |  |  | Só no arquivo da máquina: chaves que as camadas seguintes (arquivo do usuário, variáveis e argumentos) não podem mudar. |
| `locked.keys` | lista de `workers` ou `max_memory_mb` ou `data_dir` ou `output_dir` ou `temp_dir` ou `allowed_roots` ou `default_station` ou `batch_settle_seconds` ou `retention_days` ou `log_level` ou `profiles_dir` ou `ui_dir` ou `demo_dir` ou `models_dir` ou `max_upload_mb` ou `cors_origins` ou `api_token` ou `diagnostics_dir` ou `reports_dir` |  |  | Nomes das chaves travadas. |
