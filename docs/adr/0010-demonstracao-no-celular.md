# 0010: Demonstração no celular: mesma origem, entrada só com o nome e foco em quatro defeitos

Status: aceito · Data: 2026-11-09 · Decisores: Everton Ferreira
Complementa ADR-0001 (implantação) e ADR-0008 (interface).

## Contexto

Na apresentação pelo celular a interface mostrou "Failed to fetch". Reproduzimos as
causas, todas da publicação em dois endereços (interface e motor separados):

1. `QA_CORS_ORIGINS` com barra no fim (`https://….onrender.com/`, copiado da barra de
   endereços) não casa com a origem que o navegador envia: todas as respostas são
   bloqueadas;
2. respostas 401 e 500 saíam sem cabeçalho CORS (a autenticação ficava fora do CORS), e o
   navegador trocava o erro real por uma falha de rede;
3. no plano gratuito o motor dorme, e a primeira chamada falha enquanto ele acorda;
4. sem `QA_WORKERS`, o motor abria um processo de análise por núcleo da máquina
   hospedeira e estourava os 512 MB do plano gratuito;
5. a interface gravava o endereço do motor no aparelho e o reusava para sempre, por cima
   do endereço da publicação.

Além disso, no celular não se escolhe pasta e um lote realista tem dezenas de megabytes;
a tela de token atrapalhava a demonstração; e a supervisão quer ver só os casos que
importam para a triagem: página faltando, em branco, torta e sem nitidez.

## Opções consideradas

1. Corrigir só a configuração do Render (documentar CORS e variáveis).
2. Servir a interface pelo próprio motor (mesma origem) e endurecer os dois lados.
3. Empacotar tudo no navegador (WebAssembly), adiado desde o ADR-0001.

## Decisão

Opção 2.

- **Mesma origem por padrão.** A imagem Docker compila a interface com `VITE_API_URL`
  vazio e o motor a serve (`QA_UI_DIR`), montada depois das rotas da API. Um endereço só,
  sem CORS. A publicação separada continua possível.
- **CORS como camada mais externa**, por fora do tratamento de erros e da autenticação:
  toda resposta, inclusive 401 e 500, leva os cabeçalhos. Origens são normalizadas
  (sem barra, sem caminho, minúsculas).
- **Partida que espera o motor acordar**: a interface consulta `GET /health` com novas
  tentativas por até 90 s antes de qualquer outra chamada, e mostra o que está fazendo.
  Falhas de rede viram mensagens em português com o endereço usado.
- **Entrada só com o nome.** O token fica dormente: o motor informa `auth_required` em
  `GET /health` e a interface só pede o token quando `QA_API_TOKEN` está definido. A
  demonstração roda sem token; o app definitivo liga o token (e, no piloto, login
  individual).
- **Foco por perfil, não por código** (princípio 5 do ADD). O perfil `demo` liga só
  `missing_page`, `blank_page`, `skew` e `blur`, mais as regras que os sustentam
  (`out_of_order`, `numbering_review`, `completeness_unverifiable`, `corrupted_file`).
  Bordas pretas, exposição e resolução (ajustes da digitalizadora) e duplicata ficam
  desligadas. O perfil `completo` liga todas e é o da suíte de conformidade e das métricas.
- **Lote de demonstração no servidor**: `tools/synth showcase` gera no build da imagem um
  lote de 33 páginas com os quatro casos no mesmo documento (`QA_DEMO_DIR`); a interface
  oferece "Analisar lote de demonstração", sem enviar nada do aparelho. O gabarito fica
  no servidor. Contrato 0.4.0: `GET /demo-batches`, `POST /demo-batches/{name}` e
  `GET /health` com `auth_required` e `demo_batches`.
- **Padrões seguros para servidor pequeno**: `QA_WORKERS=1` na imagem; o servidor aceita
  a porta de `PORT` (Render, Fly.io, Cloud Run).
- **Toque**: botão "Ampliar" em cada miniatura (duplo clique não é confiável no
  celular), barra de navegação em duas linhas e alvos de toque de 44 px.

## Consequências

- O roteiro `ui/e2e/celular.cjs` (Pixel 7 e iPhone 13, só toque) roda na CI contra o motor
  servindo a interface; falha com erro de console, requisição que falhou, resposta 5xx
  ou rolagem horizontal.
- Sem token, qualquer pessoa com o endereço da demonstração usa o motor. Aceitável só com
  dados sintéticos e apagamento em 24 h (ADR-0001); o piloto liga `QA_API_TOKEN`.
- A imagem fica maior (interface, fontes DejaVu e ~75 MB do lote de demonstração).
- Lotes antigos guardados no navegador com o endereço do motor são ignorados (chave nova).
