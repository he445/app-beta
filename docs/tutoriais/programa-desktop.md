# Usar o programa desktop

O programa roda inteiro no computador: motor e interface numa janela, sem internet e sem
pedir administrador. Os documentos nunca saem da máquina.

## Abrir

Extraia o pacote em qualquer pasta onde você tenha permissão de escrita e abra `QA.exe`.
Não há tela de entrada: seu usuário do Windows é gravado em cada decisão.

Se o programa já estiver aberto, abrir de novo só traz a janela para a frente.

Sem o WebView2 (o motor do Edge que vem no Windows), a mesma interface abre no navegador
padrão, já autenticada. Feche a aba quando terminar; o programa se encerra sozinho depois
de algumas horas sem uso.

## Conferir uma caixa

1. **Abrir lote:** cole o caminho da pasta, local ou de rede, ou use **Escolher pasta…**.
2. Escolha o perfil e, se os arquivos não disserem de qual digitalizadora vieram, a
   estação.
3. Enquanto a digitalizadora ainda grava, o lote fica "Esperando a pasta parar de mudar".
4. Revise como na [interface de revisão](../operacao/interface.md).
5. No **Relatório**, **Salvar na pasta de saída** grava o lote corrigido em
   `Documentos\QA\Saída\<lote>-corrigido-<data-hora>`. Se a pasta original mudou durante a
   revisão, o programa recusa e diz o que mudou.

## Onde ficam as coisas

| O quê | Onde |
| --- | --- |
| Banco, cópias corrigidas, log | `%LOCALAPPDATA%\SOSDocs\QA` |
| Sua configuração | `%LOCALAPPDATA%\SOSDocs\QA\config.toml` |
| Configuração da máquina (TI) | `%PROGRAMDATA%\SOSDocs\QA\config.toml` |
| Lote corrigido | `Documentos\QA\Saída` |

Detalhes em [Configurar este computador](../guias/configurar-computador.md).

## Para o suporte

```text
QA.exe --headless                 só o motor; imprime o endereço e um link de acesso único
QA.exe --browser                  abre no navegador mesmo com WebView2
QA.exe --set log_level=debug      sobrescreve uma chave só nesta abertura
```

O log fica em `%LOCALAPPDATA%\SOSDocs\QA\logs\qa.log`; se a abertura falhar, um arquivo
`crash-<data>.txt` na mesma pasta traz a pilha de chamadas, sem caminhos do usuário.

## Rodar a partir do código

```bash
cd ui && npm ci && VITE_API_URL= npm run build && cd ..
cd engine && uv sync --extra desktop
uv run python -m qa_engine.entrypoints.desktop          # janela
uv run python -m qa_engine.entrypoints.desktop --headless
```
