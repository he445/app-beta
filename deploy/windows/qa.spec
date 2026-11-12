# PyInstaller: programa desktop em modo pasta (onedir), não arquivo único (ADR-0011).
# Dois executáveis no mesmo pacote: QA.exe (janela, sem console) e QA-suporte.exe (console,
# para suporte e para o teste de fumaça: o executável com janela não tem saída padrão).
# Construa com deploy/windows/build.ps1 (ou: pyinstaller deploy/windows/qa.spec).
# -*- mode: python -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]  # noqa: F821 - SPECPATH vem do PyInstaller
ENGINE = ROOT / "engine" / "src"
WINDOWS = sys.platform == "win32"

datas = [
    (str(ROOT / "contracts"), "contracts"),
    *collect_data_files("qa_engine", includes=["**/*.yaml", "**/*.sql"]),
]
binaries = []
hiddenimports = [
    *collect_submodules("qa_engine"),
    *collect_submodules("uvicorn"),
    "multipart",
    "python_multipart",
]
for package in ("pypdfium2", "pypdfium2_raw", "onnxruntime", "tokenizers", "reportlab"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
try:  # janela: só no pacote do programa desktop
    d, b, h = collect_all("webview")
    datas += d
    binaries += b
    hiddenimports += h
    if WINDOWS:
        for package in ("clr_loader", "pythonnet"):
            d, b, h = collect_all(package)
            datas += d
            binaries += b
            hiddenimports += h
except Exception:  # noqa: BLE001 - sem pywebview, o pacote abre no navegador
    pass

a = Analysis(  # noqa: F821
    [str(ENGINE / "qa_engine" / "entrypoints" / "desktop" / "__main__.py")],
    pathex=[str(ENGINE)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "torch"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

common = dict(
    exclude_binaries=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX é o que mais aciona antivírus
    version=str(ROOT / "deploy" / "windows" / "version.txt") if WINDOWS else None,
    icon=None,
)
gui = EXE(pyz, a.scripts, [], name="QA", console=False, **common)  # noqa: F821
console = EXE(pyz, a.scripts, [], name="QA-suporte", console=True, **common)  # noqa: F821
COLLECT(gui, console, a.binaries, a.datas, strip=False, upx=False, name="QA")  # noqa: F821
