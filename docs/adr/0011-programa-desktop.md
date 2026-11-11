# 0011: Programa desktop com PyInstaller, janela pywebview e motor em 127.0.0.1

Status: aceito · Data: 2026-11-11 · Decisores: Everton Ferreira

## Contexto

O piloto roda na estação do conferente, com documentos reais que não podem sair da
máquina, sem internet e sem pedir administrador. A demonstração já tem o motor servindo
a interface compilada na mesma origem (ADR-0010). Falta uma casca que abra esse motor
numa janela, com acesso seguro ao endereço local.

## Opções consideradas

1. **pywebview** (WebView2 do Windows) em volta do motor Python, empacotado com
   PyInstaller.
2. **Tauri**: instalador assinado e atualização automática prontos, mas exige Rust no build
   e o motor Python continua indo junto como processo auxiliar; o tamanho total quase não
   cai.
3. **Electron**: maduro, mas leva um Chromium inteiro e o Node; mais uma pilha.

## Decisão

Opção 1, isolada em `entrypoints/desktop`. Trocar por Tauri depois mexe só nesse ponto
de entrada.

Abertura (`QA.exe`):

1. `multiprocessing.freeze_support()` (sem ele, cada processo de análise abriria outra
   cópia do programa).
2. Configuração em camadas (ADR-0012). Inválida: tela de erro com a chave, a origem e o
   valor esperado, e fim (código 2).
3. Uma instância por usuário: trava de arquivo em `data_dir`. A segunda abertura pede à
   primeira, pelo endereço local e com um segredo da instância, que traga a janela para a
   frente.
4. Porta livre em `127.0.0.1` escolhida pelo sistema e token novo a cada abertura.
5. uvicorn numa thread, com a interface na mesma origem; espera `/health`.
6. Janela pywebview no endereço local. O token vai pela ponte JavaScript
   (`window.pywebview.api.get_session()`), nunca pela URL. A ponte também oferece o
   diálogo nativo de escolher pasta.
7. Sem WebView2, o navegador padrão abre com um **código de uso único** no fragmento da
   URL (`#code=...`, que não vai para o servidor nem para o log), trocado pelo token em
   `POST /session/exchange` (vale uma vez, por 2 minutos). Nesse modo o motor se encerra
   depois de 8 horas sem uso; abrir o programa de novo reabre o navegador.
8. Ao fechar a janela, o motor fecha filas, processos de análise e banco.

**Por que token no `127.0.0.1`:** qualquer site aberto no navegador da máquina pode tentar
chamar `http://127.0.0.1:<porta>`, e outros programas locais também. Por isso três travas:
token por abertura entregue pela ponte; checagem do cabeçalho `Host` (só
`127.0.0.1:<porta>` e `localhost:<porta>`, contra DNS rebinding); e nenhum CORS liberado.
O revisor vem do usuário do Windows (`GET /session`): não há senha para digitar.

`--headless` sobe só o motor e imprime um link de acesso de uso único; é o que o CI usa
para testar o fluxo no navegador e o suporte usa para diagnosticar.

## Consequências

- `pywebview` (BSD-3-Clause) entra como dependência opcional `desktop` (ADR-0004).
- Log em arquivo com rotação em `data_dir/logs`, com caminhos absolutos mascarados, e
  arquivo de queda quando a abertura falha.
- Contrato 0.7.0: `POST /session/exchange`.
- O que só se confere no Windows (janela WebView2, foco da janela existente, plano B
  quando falta WebView2) entra no teste de fumaça do executável (build Windows).
