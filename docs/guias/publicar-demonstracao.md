# Implantação

| Ambiente | Onde | Dados |
| --- | --- | --- |
| PoC / demonstração | Um contêiner num serviço de nuvem (Render, Fly.io, Railway ou Cloud Run) | Só sintéticos ou públicos; apagados em 24 h |
| Piloto | O mesmo contêiner num servidor ou VM da rede interna, aprovado pela TI | Lotes reais, sem sair da empresa |

A imagem tem **o motor e a interface na mesma origem** e um **lote de demonstração**
pronto (ADR-0010): um endereço só, que abre no celular sem CORS nem configuração da
interface.

```bash
docker build -f deploy/Dockerfile -t qa-digitalizacao .
docker run -p 8000:8000 -v qa-data:/data qa-digitalizacao
# http://localhost:8000
```

## Render (um serviço só)

1. **New → Web Service**, repositório deste projeto, runtime **Docker**.
2. **Dockerfile Path:** `./deploy/Dockerfile` · **Docker Build Context:** `.` (a raiz).
3. **Health Check Path:** `/health`.
4. Variáveis de ambiente: nenhuma é obrigatória para a demonstração. A porta vem de
   `PORT` (o Render define) e a imagem já traz `QA_WORKERS=1`, `QA_UI_DIR` e `QA_DEMO_DIR`.
5. Abra o endereço do serviço no celular. Na primeira abertura depois de um tempo parado,
   o plano gratuito acorda o motor (até ~1 minuto): a tela mostra "Acordando o motor de
   análise…" e segue sozinha.

Para exigir token (app definitivo ou piloto), defina `QA_API_TOKEN`: a interface passa a
pedir o token além do nome.

### Erros comuns que davam "Failed to fetch"

| Sintoma | Causa | Como fica agora |
| --- | --- | --- |
| Nada carrega em outro aparelho | `QA_CORS_ORIGINS` com barra no fim | Origem normalizada; e com a interface na mesma origem não há CORS |
| Token errado vira "falha de rede" | 401 sem cabeçalho CORS | CORS em toda resposta, inclusive 401 e 500 |
| Primeira chamada do dia falha | Motor dormindo no plano gratuito | A interface espera o motor acordar |
| Motor cai no meio da análise | Um processo por núcleo da máquina estoura 512 MB | `QA_WORKERS=1` na imagem |
| Um celular específico não conecta | Endereço antigo gravado no aparelho | Endereço da publicação sempre vale; botão "Usar o endereço padrão" |

## Interface e motor separados (opcional)

Para publicar a interface noutro lugar (Vercel, Netlify, Render Static Site):

```bash
cd ui && VITE_API_URL=https://qa-motor.onrender.com npm run build   # publique ui/dist/
```

e no motor `QA_CORS_ORIGINS=https://endereco-da-interface` (a barra no fim é tolerada).
Variáveis em [Instalar e rodar](../tutoriais/instalar.md).

## Plano

O plano gratuito (512 MB, CPU compartilhada) roda a demonstração de 33 páginas A5. Para
lotes A4 de 300 dpi ou análise mais rápida, use 2 a 4 GB de RAM e suba
`QA_WORKERS` para o número de núcleos dedicados.
