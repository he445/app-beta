# Referência da API

A referência é o arquivo [`contracts/openapi.yaml`](https://github.com/he445/prova-de-conceito/blob/main/contracts/openapi.yaml),
validado pelo Spectral na CI. Com o motor no ar, a interface interativa fica em
`http://localhost:8000/docs`.

| Rota | Função |
| --- | --- |
| `POST /batches` | Enviar um lote (pasta ou `.zip`), com perfil, manifesto e numeração |
| `GET /batches` | Listar lotes |
| `GET /batches/{id}` | Estado, progresso e veredito |
| `GET /batches/{id}/events` | Progresso em tempo real (Server-Sent Events) |
| `GET /batches/{id}/report` | Resultado completo com as decisões |
| `GET /batches/{id}/findings` | Sinalizações filtradas por severidade, regra e pendência |
| `POST /findings/{id}/decision` | Aprovar, corrigir (aplica na cópia), reprovar ou defeito de origem |
| `DELETE /findings/{id}/decision` | Desfazer a decisão (Ctrl+Z) |
| `POST /batches/{id}/bulk-corrections` | "Corrigir tudo" num documento ou no lote inteiro |
| `GET /batches/{id}/bulk-corrections` | Operações de correção em lote do lote |
| `GET /bulk-corrections/{id}` | Progresso real e resultado da operação |
| `DELETE /bulk-corrections/{id}?reviewer=` | Desfazer em lote só o que a operação aplicou |
| `GET /batches/{id}/corrected-plan` | Como o lote corrigido fica com as decisões atuais |
| `POST /batches/{id}/corrected-batch` | Salvar correções: gera `lote-corrigido.zip` (409 com página faltando sem decisão) |
| `GET /pages/{id}/image` | Imagem original ou corrigida |
| `PUT /pages/{id}/numbering` | Corrigir a numeração (tecla N) e ressolver a sequência |
| `GET /documents/{id}/metadata` | Metadados com fonte e confiança |
| `PUT /documents/{id}/metadata/{nome}` | Confirmar ou corrigir um metadado |
| `POST /batches/{id}/exports` | Gerar relatório, CSVs e ordem de retrabalho |
| `GET /batches/{id}/exports/{nome}` | Baixar um arquivo exportado, inclusive `lote-corrigido.zip` |
| `GET /profiles`, `GET`/`PUT /profiles/{id}` | Perfis validados contra o esquema |
| `GET /health` | Saúde (sem autenticação) |

Erros seguem o RFC 9457 (`application/problem+json`).
