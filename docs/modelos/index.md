# Modelos

Fichas (*model cards*) dos modelos de aprendizado de máquina que vão dentro do programa
desktop. Todos rodam em CPU com ONNX Runtime, sem PyTorch e sem internet.

| Modelo | Para que serve | Licença | Ficha |
| --- | --- | --- | --- |
| PP-LCNet_x1_0_doc_ori | Orientação da página (0°, 90°, 180°, 270°) | Apache-2.0 | [orientação](orientacao.md) |
| PP-OCRv5_mobile_det | Achar os escritos na região da numeração | Apache-2.0 | [detector de escritos](detector-de-escritos.md) |
| trocr-small-handwritten | Ler o número escrito à mão | MIT | [reconhecedores](reconhecedores.md) |
| PP-OCRv5_mobile_rec | Ler o número (alternativa medida pelo bench) | Apache-2.0 | [reconhecedores](reconhecedores.md) |

## Como os modelos entram no pacote

1. `models.lock.json`, na raiz do repositório, lista cada arquivo com a origem fixada por
   commit, a licença, o tamanho e o SHA-256.
2. No build, `tools/models/fetch.py` baixa os arquivos e confere o SHA-256; arquivo que
   não confere é apagado e o build falha.
3. O pacote leva `models\` e `models.lock.json` ao lado do `QA.exe`.
4. Ao abrir, o motor confere tamanho e SHA-256 de cada arquivo. Modelo ausente ou
   alterado **bloqueia a análise** (503, com a lista do que falhou, e `models` em
   `/health`), em vez de o programa seguir em silêncio sem orientação ou sem numeração.
   O teste de fumaça (`--self-test`) também confere.

Cada processo de análise carrega cada modelo uma vez e usa uma thread por sessão
(adaptador `OnnxRuntimeModel`): o paralelismo vem dos processos.

## O que cada ficha traz

Origem e versão, SHA-256, licença, para que é usado, entrada e saída, métricas medidas
(na base sintética e, quando houver, em documentos reais) e limitações conhecidas.
