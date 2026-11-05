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
uvicorn (BSD).

## Consequências

- Toda dependência nova exige registrar a licença neste ADR no mesmo PR.
- Revisão jurídica antes de qualquer distribuição comercial.
