"""Metadados do Decreto 10.278/2020 e técnicos (``docs/especificacoes/metadata.md``)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from qa_engine.application.profile import Profile, Station
from qa_engine.ports import FileMetadata

_EXIF_DT = re.compile(r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
_PDF_DT = re.compile(r"^D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?")


class MetadataSource(StrEnum):
    """De onde veio o valor de um metadado."""

    FILE_TAG = "file_tag"
    FILE_MTIME = "file_mtime"
    PROFILE = "profile"
    GENERATED = "generated"
    COMPUTED = "computed"
    OCR = "ocr"
    REVIEWER = "reviewer"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MetadataField:
    """Um metadado com fonte e confiança (tela de metadados)."""

    name: str
    value: Any
    source: MetadataSource
    confidence: float
    required_by_decree: bool = False
    confirmed: bool = False
    note: str | None = None


def parse_datetime(text: str) -> datetime | None:
    """Converte datas EXIF (``2026:11:05 10:00:00``) e PDF (``D:20261105...``) para UTC."""
    for regex in (_EXIF_DT, _PDF_DT):
        match = regex.match(text.strip())
        if match:
            y, mo, d, h, mi, sec = (int(p) if p else 0 for p in match.groups())
            try:
                return datetime(y, mo, d, h, mi, sec, tzinfo=UTC)
            except ValueError:
                return None
    return None


def match_station(stations: Sequence[Station], tags: dict[str, Any], rel: str) -> Station | None:
    """Primeira estação cujo equipamento ou pasta corresponde ao arquivo."""
    for station in stations:
        checks: list[bool] = []
        for key in ("make", "model", "serial"):
            expected = getattr(station, key)
            if expected is not None:
                checks.append(str(tags.get(key, "")).strip().lower() == expected.lower())
        if station.folder is not None:
            checks.append(rel == station.folder or rel.startswith(station.folder.rstrip("/") + "/"))
        if checks and all(checks):
            return station
    return None


def document_metadata(
    *,
    profile: Profile,
    batch_id: str,
    batch_name: str,
    document_name: str,
    document_ordinal: int,
    files: Sequence[tuple[str, FileMetadata]],
    page_count: int,
) -> list[MetadataField]:
    """Os 8 metadados mínimos do Anexo II e os técnicos do Anexo I para um documento."""
    first_rel, first = files[0]
    tags = dict(first.tags)
    fields: list[MetadataField] = []

    scanned = parse_datetime(str(tags["datetime"])) if "datetime" in tags else None
    if scanned is not None:
        fields.append(
            MetadataField("scan_date", scanned.isoformat(), MetadataSource.FILE_TAG, 0.95, True)
        )
    elif first.modified_at is not None:
        fields.append(
            MetadataField(
                "scan_date",
                first.modified_at.isoformat(),
                MetadataSource.FILE_MTIME,
                0.3,
                True,
                note="Data de modificação do arquivo: confirmar.",
            )
        )
    station = match_station(profile.stations, tags, first_rel)
    fields.append(
        MetadataField(
            "scan_location",
            station.location if station else None,
            MetadataSource.PROFILE if station else MetadataSource.UNAVAILABLE,
            0.9 if station else 0.0,
            True,
            note=None if station else "Nenhuma estação do perfil corresponde ao equipamento.",
        )
    )
    operator = tags.get("artist")
    fields.append(
        MetadataField(
            "responsible",
            profile.organization + (f" / {operator}" if operator else ""),
            MetadataSource.FILE_TAG if operator else MetadataSource.PROFILE,
            0.8 if operator else 0.6,
            True,
            note=None if operator else "Operador não gravado no arquivo: informar ao abrir o lote.",
        )
    )
    identifier = profile.identifier_pattern.format(
        batch=batch_name, document=document_name.replace("/", "-"), seq=f"{document_ordinal:04d}"
    )
    fields.append(MetadataField("identifier", identifier, MetadataSource.GENERATED, 1.0, True))
    fields.append(
        MetadataField(
            "hash_sha256",
            first.sha256 if len(files) == 1 else {rel: m.sha256 for rel, m in files},
            MetadataSource.COMPUTED,
            1.0,
            True,
        )
    )
    for name in ("title", "document_type", "author", "subject"):
        fields.append(
            MetadataField(
                name,
                None,
                MetadataSource.UNAVAILABLE,
                0.0,
                True,
                note="Sugestão por OCR prevista no adaptador OcrEngine (fase seguinte).",
            )
        )

    technical = {
        "make": tags.get("make"),
        "model": tags.get("model"),
        "software": tags.get("software"),
        "dpi": tags.get("dpi"),
        "color_mode": tags.get("mode"),
        "bit_depth": tags.get("bits"),
        "compression": tags.get("compression"),
        "format": first.format,
        "page_count": page_count,
        "size_bytes": sum(m.size_bytes for _, m in files),
    }
    if tags.get("dpi") and tags.get("width_px"):
        dpi = float(tags["dpi"])
        technical["width_mm"] = round(float(tags["width_px"]) / dpi * 25.4, 1)
        technical["height_mm"] = round(float(tags["height_px"]) / dpi * 25.4, 1)
    for name, value in technical.items():
        fields.append(
            MetadataField(
                name,
                value,
                MetadataSource.FILE_TAG if value is not None else MetadataSource.UNAVAILABLE,
                1.0 if value is not None else 0.0,
            )
        )
    return fields
