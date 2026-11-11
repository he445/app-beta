# Licenças de terceiros

Regra (ADR-0004): nada GPL ou AGPL ligado ao processo do motor. Bibliotecas ligadas ao
motor têm licença permissiva ou de cópia fraca por arquivo; ferramenta GPL só roda como
processo externo, atrás de uma porta. Dependência nova entra no ADR-0004 no mesmo commit.

## Motor

| Função | Dependência | Licença |
| --- | --- | --- |
| Matrizes | NumPy | BSD-3-Clause |
| Visão computacional | OpenCV (`opencv-python-headless`) | Apache-2.0 |
| Leitura e gravação de imagens | Pillow | MIT-CMU |
| Renderização de PDF | pypdfium2 (PDFium) | Apache-2.0 / BSD-3-Clause |
| Perfis e manifestos | PyYAML | MIT |
| Validação contra o contrato | jsonschema | MIT |
| API HTTP | FastAPI, Starlette | MIT |
| Servidor HTTP | uvicorn | BSD-3-Clause |
| Envio de arquivos | python-multipart | Apache-2.0 |
| Pastas do sistema operacional | platformdirs | MIT |
| Janela do programa desktop | pywebview (e, no Windows, pythonnet e clr-loader) | BSD-3-Clause (MIT) |
| Armazenamento | SQLite (biblioteca padrão do Python) | Domínio público |

PyMuPDF (AGPL) não é usado.

## Interface

| Função | Dependência | Licença |
| --- | --- | --- |
| Interface | React, React DOM | MIT |
| Estado de servidor | TanStack Query | MIT |
| Zoom profundo | OpenSeadragon | BSD-3-Clause |

## Desenvolvimento (não vão no pacote)

pytest e Hypothesis (MIT, MPL-2.0), Ruff e mypy (MIT), Vite, Vitest e TypeScript (MIT,
Apache-2.0), openapi-typescript (MIT), Playwright (Apache-2.0), MkDocs Material e
mkdocstrings (MIT, ISC), Spectral e oasdiff (Apache-2.0). PyInstaller (GPL-2.0+ com
exceção para o executável gerado) só monta o pacote.

As licenças precisam ser revistas por alguém do jurídico antes de qualquer distribuição
comercial.
