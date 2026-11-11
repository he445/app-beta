# 0004: Nada AGPL ou GPL ligado ao núcleo

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

O código pode virar produto fechado no futuro. Algumas ferramentas de referência são GPL
(ExifTool, veraPDF em uma das licenças) ou AGPL (PyMuPDF).

## Decisão

- Bibliotecas ligadas ao processo do motor: só licenças permissivas ou de cópia fraca
  por arquivo (Apache-2.0, MIT, BSD, PSF, MPL-2.0, LGPL usada como biblioteca dinâmica).
- Ferramentas GPL rodam como **processo externo** atrás de uma porta (veraPDF, ExifTool).
- PyMuPDF (AGPL) não é usado: PDF é renderizado com pypdfium2 (Apache-2.0/BSD-3).

Dependências atuais do núcleo: NumPy (BSD), OpenCV (Apache-2.0), Pillow (MIT-CMU),
pypdfium2 (Apache-2.0/BSD-3), PyYAML (MIT), jsonschema (MIT), FastAPI/Starlette (MIT),
uvicorn (BSD), python-multipart (Apache-2.0), platformdirs (MIT).

Modelos e inferência: onnxruntime (MIT), tokenizers (Apache-2.0); modelos
PP-LCNet_x1_0_doc_ori, PP-OCRv5_mobile_det e PP-OCRv5_mobile_rec (Apache-2.0) e
trocr-small-handwritten (MIT), listados com SHA-256 em `models.lock.json`. Nada de
PyTorch no pacote.

Programa desktop: pywebview (BSD-3-Clause), opcional, só no pacote Windows; no Windows
ele traz pythonnet e clr-loader (MIT).

Ferramentas só de build, que não vão no pacote como biblioteca: PyInstaller (GPL-2.0 ou
posterior **com exceção** que permite distribuir o executável gerado sob qualquer
licença; o bootloader embutido é coberto por essa exceção).

## Consequências

- Toda dependência nova exige registrar a licença neste ADR no mesmo PR.
- Revisão jurídica antes de qualquer distribuição comercial.
