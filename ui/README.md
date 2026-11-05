# Interface web (próximo incremento)

Ainda não implementada. Escopo, na ordem de prioridade para a demonstração:

1. Enviar lote (pasta ou `.zip`, perfil, manifesto) com o aviso de que documento de cliente
   é proibido.
2. Processamento ao vivo (`GET /batches/{id}/events`).
3. Painel do lote: veredito, contagens, % que dispensa revisão, defeitos por estação.
4. Fila de revisão por teclado (A, C, R, O, setas, espaço, Ctrl+Z, 1–4, N), meta de uma
   decisão por segundo.
5. Detalhe da página com a região destacada, medida, limiar e antes/depois.
6. Sequência do documento com a numeração lida e a reordenação proposta.
7. Metadados editáveis, relatório e ordem de retrabalho, perfis.

Pilha (seção 14 do ADD): React + TypeScript + Vite, TanStack Query, OpenSeadragon, tipos
gerados de `contracts/openapi.yaml` com openapi-typescript. Site estático; fala com o
motor só pela API.
