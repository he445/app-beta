"""Página duplicada: dHash, correlação de miniaturas e comparação alinhada.

Especificação: ``docs/especificacoes/detectors/duplicate_page.md``.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from qa_engine.detectors.base import Params
from qa_engine.ports import as_u8

ID = "duplicate_page"
THUMB_WIDTH = 128
THUMB_SIGMA = 1.0
HASH_SIZE = 16
ALIGN_WIDTH = 256
"""Largura da vista usada na comparação alinhada."""
ALIGN_SIGMA = 1.5
"""Suavização da vista antes da correlação (tolera o ruído de cada passada)."""
INK_WIDTH = 512
"""Largura da máscara de tinta da segunda checagem: o preenchimento de um formulário só
aparece com essa resolução."""
INK_TOLERANCE = 2
"""Pixels da máscara em que o traço de uma página pode estar deslocado do da outra."""
INK_MARGIN = 0.04
"""Moldura ignorada na segunda checagem (borda do digitalizador, conteúdo que sai da folha)."""
MAX_ROTATION = 3.0
ROTATION_STEP = 0.5
MIN_OVERLAP = 0.5
"""Fração mínima da vista que precisa se sobrepor depois do alinhamento."""
COARSE_SHAPE = (THUMB_WIDTH, 176)
"""Miniatura do filtro grosso, de tamanho fixo: a correlação vira um produto escalar."""


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """Impressão digital de uma página para comparação."""

    page_id: str
    dhash: int
    thumb: NDArray[np.uint8]
    sharpness: float
    eligible: bool
    view_png: bytes = b""
    """Vista de ``ALIGN_WIDTH`` px de largura, em PNG (comparação alinhada)."""
    ink_png: bytes = b""
    """Máscara de tinta com ``INK_WIDTH`` px de largura, em PNG (segunda checagem)."""
    raster_hash: str | None = None
    """Hash do raster decodificado: cópia exata, sem depender de tinta."""


@dataclass(frozen=True, slots=True)
class DuplicatePair:
    """Par de páginas quase idênticas; ``copy`` é a que sai."""

    copy: str
    original: str
    similarity: float
    hash_distance: int
    copy_first: bool = False
    """A cópia vem antes do original no lote: a página que fica ocupa a posição dela."""
    ink_difference: float = 0.0


def views(gray: NDArray[np.uint8], ink: NDArray[np.bool_]) -> tuple[bytes, bytes]:
    """Vista e máscara de tinta reduzidas para a comparação alinhada, em PNG."""
    h, w = gray.shape
    view = cv2.resize(gray, _size(w, h, ALIGN_WIDTH), interpolation=cv2.INTER_AREA)
    mask = (
        cv2.resize(ink.astype(np.uint8) * 255, _size(w, h, INK_WIDTH), interpolation=cv2.INTER_AREA)
        > 64
    )
    return _png(view), _png(mask.astype(np.uint8) * 255)


def _size(w: int, h: int, width: int) -> tuple[int, int]:
    return width, max(1, round(h * width / w))


def raster_hash(gray: NDArray[np.uint8]) -> str:
    """Hash do raster de análise (cópia exata)."""
    return hashlib.blake2b(gray.tobytes() + str(gray.shape).encode(), digest_size=16).hexdigest()


def aligned_comparison(
    a: NDArray[np.uint8], ia: NDArray[np.bool_], b: NDArray[np.uint8], ib: NDArray[np.bool_]
) -> tuple[float, float]:
    """Semelhança depois de alinhar ``b`` em ``a`` (giro e deslocamento) e diferença de tinta.

    Para cada giro de −3° a +3°, o deslocamento sai da correlação de fase (janela de Hann);
    a semelhança é a correlação normalizada só na área que se sobrepõe. A diferença de
    tinta, no melhor alinhamento e na máscara de ``INK_WIDTH`` px, é a fração do traço de
    uma página sem traço da outra a até ``INK_TOLERANCE`` pixels, fora da moldura.

    Args:
        a: vista da primeira página (``ALIGN_WIDTH`` px de largura).
        ia: máscara de tinta da primeira página (``INK_WIDTH`` px de largura).
        b: vista da segunda página.
        ib: máscara de tinta da segunda página.

    Returns:
        ``(semelhança, diferença_de_tinta)``.
    """
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    fa, fb = _smooth(a[:h, :w]), _smooth(b[:h, :w])
    window = cv2.createHanningWindow((w, h), cv2.CV_32F)
    center = (w / 2, h / 2)
    best_sim, best_m = -1.0, None
    for angle in np.arange(-MAX_ROTATION, MAX_ROTATION + 1e-6, ROTATION_STEP):
        m = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        turned = cv2.warpAffine(fb, m, (w, h))
        (dx, dy), _ = cv2.phaseCorrelate(fa, turned, window)
        m[0, 2] -= dx
        m[1, 2] -= dy
        moved = cv2.warpAffine(fb, m, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=np.nan)
        overlap = ~np.isnan(moved)
        if overlap.sum() < MIN_OVERLAP * w * h:
            continue
        x = fa[overlap] - fa[overlap].mean()
        y = moved[overlap] - moved[overlap].mean()
        denom = math.sqrt(float((x * x).sum()) * float((y * y).sum()))
        sim = float((x * y).sum()) / denom if denom > 0 else 0.0
        if sim > best_sim:
            best_sim, best_m = sim, m
    if best_m is None:
        return 0.0, 1.0
    return best_sim, _ink_difference(ia, ib, best_m, INK_WIDTH / ALIGN_WIDTH)


def _ink_difference(
    ia: NDArray[np.bool_], ib: NDArray[np.bool_], m: NDArray[np.float64], scale: float
) -> float:
    """Fração do traço sem correspondência na outra página, com a transformação achada."""
    h = min(ia.shape[0], ib.shape[0])
    w = min(ia.shape[1], ib.shape[1])
    ia, ib = ia[:h, :w], ib[:h, :w]
    m = m.copy()
    m[:, 2] *= scale  # o mesmo giro e deslocamento na escala da máscara
    moved = cv2.warpAffine(ib.astype(np.uint8), m, (w, h), flags=cv2.INTER_NEAREST) > 0
    valid = cv2.warpAffine(np.ones((h, w), np.uint8), m, (w, h), flags=cv2.INTER_NEAREST) > 0
    margin = round(INK_MARGIN * min(h, w))
    core = np.zeros((h, w), dtype=bool)
    core[margin : h - margin, margin : w - margin] = True
    valid &= core
    a_ink, b_ink = ia & valid, moved & valid
    kernel = np.ones((2 * INK_TOLERANCE + 1, 2 * INK_TOLERANCE + 1), np.uint8)
    near_a = cv2.dilate(a_ink.astype(np.uint8), kernel) > 0
    near_b = cv2.dilate(b_ink.astype(np.uint8), kernel) > 0
    total = int(a_ink.sum() + b_ink.sum())
    missing = int((a_ink & ~near_b).sum() + (b_ink & ~near_a).sum())
    return missing / total if total else 0.0


def _unit(thumb: NDArray[np.uint8]) -> NDArray[np.float32]:
    """Miniatura em tamanho fixo, com média zero e norma 1 (correlação = produto escalar)."""
    v = cv2.resize(thumb, COARSE_SHAPE, interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    v -= v.mean()
    norm = float(np.linalg.norm(v))
    return np.asarray(v / norm if norm > 0 else v, dtype=np.float32)


def _smooth(gray: NDArray[np.uint8]) -> NDArray[np.float32]:
    out = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), ALIGN_SIGMA)
    return np.asarray(out, dtype=np.float32)


def _png(gray: NDArray[np.uint8]) -> bytes:
    ok, data = cv2.imencode(".png", gray)
    return data.tobytes() if ok else b""


def _decode(data: bytes) -> NDArray[np.uint8]:
    out = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    return as_u8(out if out is not None else np.zeros((1, 1), np.uint8))


def dhash(gray: NDArray[np.uint8], size: int = HASH_SIZE) -> int:
    """Hash de diferença de ``size`` × ``size`` bits."""
    small = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def thumbnail(gray: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Miniatura de largura fixa, suavizada, usada na verificação por correlação.

    A suavização torna a comparação tolerante ao deslocamento de poucos pixels
    entre duas capturas da mesma folha.
    """
    h, w = gray.shape
    height = max(1, round(h * THUMB_WIDTH / w))
    small = cv2.resize(gray, (THUMB_WIDTH, height), interpolation=cv2.INTER_AREA)
    return as_u8(cv2.GaussianBlur(small, (0, 0), THUMB_SIGMA))


def _ncc(a: NDArray[np.uint8], b: NDArray[np.uint8]) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    x = a.astype(np.float64) - a.mean()
    y = b.astype(np.float64) - b.mean()
    denom = float(np.sqrt((x * x).sum() * (y * y).sum()))
    return float((x * y).sum() / denom) if denom > 0 else 0.0


def find_duplicates(
    prints: Sequence[Fingerprint],
    params: Params,
    params_of: Callable[[str], Params] | None = None,
    folio_of: Callable[[str], str | None] | None = None,
) -> list[DuplicatePair]:
    """Compara os pares do lote: hash exato, filtro grosso e comparação alinhada.

    O filtro grosso (dHash e correlação das miniaturas sem alinhar) só escolhe os candidatos;
    quem confirma é a comparação alinhada, seguida da diferença de tinta (formulário
    repetido com preenchimento diferente não é duplicata) e do veto pela numeração.

    Args:
        prints: impressões digitais das páginas, na ordem do lote.
        params: parâmetros do perfil.
        params_of: parâmetros por página, quando a estação dela ajusta a regra; o par é
            julgado com os da página que seria a cópia.
        folio_of: número de folha lido com confiança alta numa página, ou ``None``.
    """
    max_bits = int(params["max_hash_distance"])
    min_sim = float(params["min_similarity"])
    if params_of is not None:
        each = [params_of(p.page_id) for p in prints if p.eligible]
        max_bits = max([max_bits, *(int(e["max_hash_distance"]) for e in each)])
        min_sim = min([min_sim, *(float(e["min_similarity"]) for e in each)])
    candidate_at = float(params.get("candidate_min_similarity", 0.6))
    max_ink = float(params.get("max_ink_difference", 0.05))
    margin = float(params.get("sharpness_margin", 0.8))
    decoded: dict[str, tuple[NDArray[np.uint8], NDArray[np.bool_]] | None] = {}
    coarse_vec: dict[str, NDArray[np.float32]] = {}

    def coarse_of(a: Fingerprint, b: Fingerprint) -> float:
        for p in (a, b):
            if p.page_id not in coarse_vec:
                coarse_vec[p.page_id] = _unit(p.thumb)
        return float(coarse_vec[a.page_id] @ coarse_vec[b.page_id])

    def view_of(p: Fingerprint) -> tuple[NDArray[np.uint8], NDArray[np.bool_]] | None:
        if p.page_id not in decoded:
            decoded[p.page_id] = (
                (_decode(p.view_png), _decode(p.ink_png) > 0) if p.view_png and p.ink_png else None
            )
        return decoded[p.page_id]

    pairs: list[DuplicatePair] = []
    flagged: set[str] = set()
    for i, first in enumerate(prints):
        for second in prints[i + 1 :]:
            exact = first.raster_hash is not None and first.raster_hash == second.raster_hash
            ink_difference = 0.0
            if exact:
                distance, similarity = 0, 1.0
            else:
                if not (first.eligible and second.eligible):
                    continue
                distance = (first.dhash ^ second.dhash).bit_count()
                if distance > max_bits:
                    continue
                va, vb = view_of(first), view_of(second)
                if va is None or vb is None:
                    similarity = _ncc(first.thumb, second.thumb)  # sem vista: comparação antiga
                else:
                    if coarse_of(first, second) < candidate_at:
                        continue
                    similarity, ink_difference = aligned_comparison(va[0], va[1], vb[0], vb[1])
                if similarity < min_sim:
                    continue
                if va is not None and vb is not None and ink_difference > max_ink:
                    continue  # mesmo formulário, preenchimento diferente
            if folio_of is not None:
                fa, fb = folio_of(first.page_id), folio_of(second.page_id)
                if fa is not None and fb is not None and fa != fb:
                    continue  # números de folha diferentes lidos com confiança: não é cópia
            copy, original = _choose_copy(first, second, margin)
            if params_of is not None and not exact:
                own = params_of(copy.page_id)
                if distance > int(own["max_hash_distance"]):
                    continue
                if similarity < float(own["min_similarity"]):
                    continue
            if copy.page_id in flagged:
                continue
            flagged.add(copy.page_id)
            pairs.append(
                DuplicatePair(
                    copy.page_id,
                    original.page_id,
                    similarity,
                    distance,
                    copy_first=copy is first,
                    ink_difference=ink_difference,
                )
            )
    return pairs


def _choose_copy(
    first: Fingerprint, second: Fingerprint, margin: float
) -> tuple[Fingerprint, Fingerprint]:
    """Qual das duas sai: a segunda ocorrência, a não ser que a outra seja claramente pior.

    Com nitidez parecida (razão de pelo menos ``margin``), sai a que vem depois. Se uma for
    claramente menos nítida, sai ela.
    """
    low, high = sorted((first.sharpness, second.sharpness))
    if high <= 0 or low / high >= margin:
        return second, first
    return (first, second) if first.sharpness < second.sharpness else (second, first)
