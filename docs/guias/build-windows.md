# Gerar o build Windows

O programa desktop é empacotado com PyInstaller em modo **pasta** (`onedir`), não em
arquivo único: o arquivo único se descompacta numa pasta temporária a cada abertura, abre
mais devagar e é o formato que antivírus mais estranham (ADR-0011).

## Pacote

```text
QA-SOS-Docs-<versão>\
  QA.exe              janela (sem console)
  QA-suporte.exe      o mesmo programa com console: suporte e teste de fumaça
  _internal\          motor Python, OpenCV, PDFium, contrato
  ui\                 interface compilada
  profiles\           demo.yaml, completo.yaml, sos-piloto.yaml
  samples\            lote de exemplo do teste de fumaça (com gabarito)
  docs\               esta documentação, para ler sem internet
  LEIA-ME.txt
```

Dois executáveis porque o executável com janela não tem saída padrão: o teste de fumaça
e o suporte precisam ler o resultado.

## No CI

`.github/workflows/windows.yml`, em `windows-latest`, roda em tag `v*`, à mão (Actions →
Windows → Run workflow) e quando muda o que afeta o pacote:

1. testes do motor e suíte de conformidade **em Windows**;
2. `deploy/windows/build.ps1`: interface, lote de exemplo, documentação offline,
   PyInstaller, recursos ao lado do `QA.exe`, teste de fumaça e zip com SHA-256;
3. o programa sem janela responde em `/health` e a segunda abertura não sobe outro motor;
4. o zip e o `.sha256` ficam como artefato do workflow.

## Na sua máquina Windows

Requisitos: [uv](https://docs.astral.sh/uv/), Node 22 e as fontes DejaVu (para o lote de
exemplo), com `QA_SYNTH_FONT_DIR` apontando para a pasta `ttf`.

```powershell
powershell -ExecutionPolicy Bypass -File deploy/windows/build.ps1
```

O resultado fica em `build\dist\QA-SOS-Docs-<versão>.zip`.

## Teste de fumaça

```powershell
QA-suporte.exe --self-test            # lote de exemplo do pacote
QA-suporte.exe --self-test D:\Lote    # outra pasta com gabarito.json
```

Analisa o lote com processos de análise de verdade (é onde um executável mal empacotado
quebra), confere o gabarito, confere se a interface e os perfis estão no pacote e mede o
custo por página. Imprime uma linha JSON e sai com 0 se tudo conferiu. O CI falha se o
custo passar de 3 vezes o orçamento (`--budget-ms`, padrão 1000 ms): a máquina do CI não
é a estação, e o limite absoluto é conferido na máquina do piloto
([Testes](../testes/index.md)).

## Assinatura e antivírus

Executável sem assinatura digital aciona o SmartScreen e heurísticas de antivírus. Para
o piloto, o caminho é liberar o programa com a TI pelo SHA-256 do zip ou pela pasta; para
distribuir em mais máquinas, um certificado de assinatura de código. O build não usa UPX,
que é o que mais aciona antivírus.
