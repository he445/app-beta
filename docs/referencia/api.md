<!-- Gerado por tools/docs/gen_reference.py. Não edite: mude a fonte e gere de novo. -->

# Referência da API

Contrato **0.8.0**. A fonte é `contracts/openapi.yaml`, com os
formatos em `contracts/schemas/` (JSON Schema 2020-12), validados pelo Spectral na CI.
Com o motor no ar, a versão interativa fica em `/docs`.

Erros seguem o RFC 9457 (`application/problem+json`).

## Envio, progresso e resultado de lotes

| Rota | Função | Respostas |
| --- | --- | --- |
| `GET /batches` | Listar lotes | 200, 401 |
| `POST /batches` | Enviar um lote | 202, 400, 401, 413 |
| `GET /demo-batches` | Lotes de demonstração prontos no servidor | 200, 401 |
| `POST /demo-batches/{name}` | Analisar um lote de demonstração (sem enviar arquivos) | 202, 401, 404 |
| `POST /local-batches` | Abrir um lote numa pasta local ou de rede (só no programa desktop) | 202, 401, 403, 404, 422 |
| `GET /batches/{batch_id}` | Estado, progresso e veredito | 200, 401, 404 |
| `GET /batches/{batch_id}/events` | Progresso em tempo real (Server-Sent Events) | 200, 401, 404 |
| `GET /batches/{batch_id}/report` | Resultado completo, com as decisões registradas | 200, 401, 404, 409 |
| `GET /documents/{document_id}/metadata` | Metadados com fonte e confiança | 200, 401, 404 |
| `PUT /documents/{document_id}/metadata/{name}` | Confirmar ou corrigir um metadado (tela 7) | 200, 401, 404 |
| `POST /batches/{batch_id}/exports` | Gerar relatório, CSVs, JSON de metadados e ordem de retrabalho | 201, 401, 404, 409 |
| `GET /batches/{batch_id}/exports/{name}` | Baixar um arquivo exportado | 200, 401, 404 |

## Decisões do revisor

| Rota | Função | Respostas |
| --- | --- | --- |
| `GET /batches/{batch_id}/findings` | Sinalizações filtradas por severidade, regra e pendência | 200, 401, 404 |
| `POST /findings/{finding_id}/decision` | Aprovar, corrigir, reprovar ou marcar defeito de origem | 200, 401, 404, 422 |
| `DELETE /findings/{finding_id}/decision` | Desfazer a última decisão (Ctrl+Z) | 200, 401, 404, 409 |

## Imagens e numeração

| Rota | Função | Respostas |
| --- | --- | --- |
| `GET /pages/{page_id}/image` | Imagem da página, original ou corrigida | 200, 401, 404 |
| `PUT /pages/{page_id}/numbering` | Confirmar ou corrigir a numeração lida (tecla N) | 200, 401, 404, 422 |

## Correção em lote ("Corrigir tudo") e lote corrigido para baixar

| Rota | Função | Respostas |
| --- | --- | --- |
| `GET /batches/{batch_id}/bulk-corrections` | Operações de correção em lote do lote, da mais recente à mais antiga | 200, 401, 404 |
| `POST /batches/{batch_id}/bulk-corrections` | Corrigir tudo (documento ou lote inteiro) | 202, 401, 404, 409, 422 |
| `GET /bulk-corrections/{operation_id}` | Progresso e resultado de uma correção em lote | 200, 401, 404 |
| `DELETE /bulk-corrections/{operation_id}` | Desfazer em lote só o que esta operação aplicou | 200, 401, 404, 409 |
| `GET /batches/{batch_id}/corrected-plan` | Como o lote corrigido vai ficar com as decisões atuais | 200, 401, 404, 409 |
| `POST /batches/{batch_id}/corrected-batch` | Salvar correções e gerar o lote corrigido (.zip ou pasta) | 201, 401, 404, 409 |

## Perfis de cliente

| Rota | Função | Respostas |
| --- | --- | --- |
| `GET /profiles` | Listar perfis | 200, 401 |
| `GET /profiles/{profile_id}/rules` | Regras do perfil para uma estação, com a origem de cada valor | 200, 401, 404 |
| `GET /profiles/{profile_id}` | Ler um perfil | 200, 401, 404 |
| `PUT /profiles/{profile_id}` | Criar ou atualizar um perfil (validado contra o esquema) | 200, 401, 422 |

## Saúde do serviço

| Rota | Função | Respostas |
| --- | --- | --- |
| `GET /health` | Saúde do serviço | 200 |
| `GET /settings` | Configuração deste computador, com a origem de cada valor | 200, 401, 404 |
| `PUT /settings` | Mudar a configuração do usuário | 200, 401, 404, 422 |
| `POST /session/exchange` | Trocar o código de uso único pelo token (programa desktop no navegador) | 200, 403, 404 |
| `GET /session` | Quem está usando o motor | 200, 401 |
