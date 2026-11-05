# Implantação

| Ambiente | Onde | Dados |
| --- | --- | --- |
| PoC | Contêiner num serviço de nuvem (Render, Fly.io, Railway ou Cloud Run), 2 a 4 GB de RAM, sem GPU | Só sintéticos ou públicos; apagados em 24 h |
| Piloto | O mesmo contêiner num servidor ou VM da rede interna, aprovado pela TI | Lotes reais, sem sair da empresa |

```bash
docker build -f deploy/Dockerfile -t qa-engine .
docker run -p 8000:8000 -v qa-data:/data \
  -e QA_API_TOKEN=troque-isto -e QA_CORS_ORIGINS=https://interface.exemplo \
  qa-engine
```

Variáveis em [docs/guides/instalar.md](../docs/guides/instalar.md). Em produção, defina
sempre `QA_API_TOKEN` e `QA_CORS_ORIGINS` e sirva atrás de HTTPS.
