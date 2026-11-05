"""``ImageSource`` com Pillow (TIFF, JPG, PNG) e pypdfium2 (PDF)."""

from __future__ import annotations

import warnings
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from numpy.typing import NDArray
from PIL import Image, ImageSequence, UnidentifiedImageError

from qa_engine.domain.model import ColorMode
from qa_engine.ports import LoadedPage, LoadError, as_u8

IMAGE_SUFFIXES = {".tif", ".tiff", ".jpg", ".jpeg", ".png"}
PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = IMAGE_SUFFIXES | PDF_SUFFIXES
A4_SHORT_SIDE_MM = 210.0
Image.MAX_IMAGE_PIXELS = 400_000_000


def _color_mode(mode: str) -> ColorMode:
    if mode == "1":
        return ColorMode.BILEVEL
    if mode in {"L", "LA", "I", "I;16", "I;16B", "F"}:
        return ColorMode.GRAY
    return ColorMode.RGB


def _saturation(rgb: NDArray[np.uint8]) -> float:
    small = cv2.resize(rgb, (256, max(1, round(256 * rgb.shape[0] / rgb.shape[1]))))
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    return float(hsv[:, :, 1].mean() / 255.0)


def _reduce(gray: NDArray[np.uint8], scale: float) -> NDArray[np.uint8]:
    if abs(scale - 1.0) < 1e-6:
        return gray
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    h, w = gray.shape
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return as_u8(cv2.resize(gray, size, interpolation=interp))


def _scale_for(dpi: float | None, width: int, height: int, analysis_dpi: float) -> float:
    if dpi:
        return analysis_dpi / dpi
    # Sem DPI gravado: assume que o lado menor é o de uma folha A4.
    return analysis_dpi * A4_SHORT_SIDE_MM / 25.4 / min(width, height)


class FileImageSource:
    """Lê imagens com Pillow e PDF com PDFium, por extensão do arquivo."""

    def page_count(self, path: Path) -> int:
        """Número de páginas; :class:`LoadError` se o arquivo estiver ilegível."""
        _check_size(path)
        suffix = path.suffix.lower()
        try:
            if suffix in PDF_SUFFIXES:
                with _open_pdf(path) as pdf:
                    return len(pdf)
            with Image.open(path) as img:
                return sum(1 for _ in ImageSequence.Iterator(img))
        except (OSError, UnidentifiedImageError, pdfium.PdfiumError, ValueError) as exc:
            raise LoadError(_reason(exc, path)) from exc

    def load(self, path: Path, page_in_file: int, analysis_dpi: float) -> LoadedPage:
        """Decodifica e reduz uma página para análise."""
        try:
            with warnings.catch_warnings():
                # Avisos do Pillow sobre tags corrompidas viram falha explícita, não ruído.
                warnings.simplefilter("ignore")
                if path.suffix.lower() in PDF_SUFFIXES:
                    return self._load_pdf(path, page_in_file, analysis_dpi)
                return self._load_image(path, page_in_file, analysis_dpi)
        except LoadError:
            raise
        except (OSError, UnidentifiedImageError, pdfium.PdfiumError, ValueError) as exc:
            raise LoadError(_reason(exc, path)) from exc

    def load_original(self, path: Path, page_in_file: int) -> NDArray[np.uint8]:
        """Página em resolução original: cinza (2D) ou RGB (3D)."""
        try:
            if path.suffix.lower() in PDF_SUFFIXES:
                with _open_pdf(path) as pdf:
                    page = pdf[page_in_file]
                    bitmap = page.render(scale=300 / 72).to_numpy()
                    return np.ascontiguousarray(bitmap[:, :, :3][:, :, ::-1])
            with Image.open(path) as img:
                img.seek(page_in_file)
                if img.mode in {"1", "L", "I;16", "I"}:
                    return np.asarray(img.convert("L"))
                return np.asarray(img.convert("RGB"))
        except (OSError, UnidentifiedImageError, pdfium.PdfiumError, ValueError) as exc:
            raise LoadError(_reason(exc, path)) from exc

    def _load_image(self, path: Path, page_in_file: int, analysis_dpi: float) -> LoadedPage:
        with Image.open(path) as img:
            img.seek(page_in_file)
            img.load()
            dpi_info = img.info.get("dpi")
            dpi = float(dpi_info[0]) if dpi_info and float(dpi_info[0]) > 1 else None
            mode = _color_mode(img.mode)
            saturation = None
            if mode is ColorMode.RGB:
                saturation = _saturation(np.asarray(img.convert("RGB")))
            gray = np.asarray(img.convert("L"))
        h, w = gray.shape
        scale = _scale_for(dpi, w, h, analysis_dpi)
        return LoadedPage(_reduce(gray, scale), scale, w, h, dpi, mode, saturation)

    def _load_pdf(self, path: Path, page_in_file: int, analysis_dpi: float) -> LoadedPage:
        with _open_pdf(path) as pdf:
            page = pdf[page_in_file]
            width_pt, height_pt = page.get_size()
            dpi = _pdf_image_dpi(page)
            bitmap = page.render(scale=analysis_dpi / 72, grayscale=True).to_numpy()
            gray = np.ascontiguousarray(bitmap if bitmap.ndim == 2 else bitmap[:, :, 0])
        # Dimensões "originais" de um PDF: as da imagem embutida, ou a página a 300 dpi.
        ref_dpi = dpi or 300.0
        w, h = round(width_pt / 72 * ref_dpi), round(height_pt / 72 * ref_dpi)
        return LoadedPage(gray, analysis_dpi / ref_dpi, w, h, dpi, None, None)


class _PdfHandle:
    def __init__(self, path: Path) -> None:
        self.pdf = pdfium.PdfDocument(str(path))

    def __enter__(self) -> pdfium.PdfDocument:
        return self.pdf

    def __exit__(self, *args: object) -> None:
        self.pdf.close()


def _open_pdf(path: Path) -> _PdfHandle:
    return _PdfHandle(path)


def _pdf_image_dpi(page: pdfium.PdfPage) -> float | None:
    """DPI da maior imagem embutida na página (PDF de digitalização)."""
    best: tuple[float, float] | None = None
    for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,), max_depth=2):
        meta = obj.get_metadata()
        area = float(meta.width * meta.height)
        if meta.horizontal_dpi > 0 and (best is None or area > best[0]):
            best = (area, float(meta.horizontal_dpi))
    return round(best[1], 1) if best else None


def _check_size(path: Path) -> None:
    if path.stat().st_size == 0:
        raise LoadError("arquivo vazio (0 byte)")


def _reason(exc: BaseException, path: Path) -> str:
    """Motivo curto, sem caminhos do servidor."""
    text = (str(exc).strip() or exc.__class__.__name__).replace(str(path), path.name)
    return text[:200]
