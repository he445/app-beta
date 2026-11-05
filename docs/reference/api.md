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
| `GET /pages/{id}/image` | Imagem original ou corrigida |
| `PUT /pages/{id}/numbering` | Corrigir a numeração (tecla N) e ressolver a sequência |
| `GET /documents/{id}/metadata` | Metadados com fonte e confiança |
| `POST /batches/{id}/exports` | Gerar relatório, CSVs e ordem de retrabalho |
| `GET /batches/{id}/exports/{nome}` | Baixar um arquivo exportado |
| `GET /profiles`, `GET`/`PUT /profiles/{id}` | Perfis validados contra o esquema |
| `GET /health` | Saúde (sem autenticação) |

Erros seguem o RFC 9457 (`application/problem+json`).
