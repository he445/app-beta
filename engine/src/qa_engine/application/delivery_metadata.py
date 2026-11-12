"""Metadados do Decreto 10.278/2020 no lote corrigido.

Especificação: ``docs/especificacoes/metadata.md`` (seção "No lote corrigido"). Cada
página entregue leva as tags técnicas do original, a marca de que passou pelo programa
(e qual correção) nas tags de software e data, e um XMP com os campos do Decreto. Cada
processo ganha ``metadados/<processo>.json`` com o valor e a origem de cada campo, e o
lote ganha ``hashes.sha256`` com o SHA-256 de cada arquivo entregue.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape

DECREE_FIELDS = (
    "scan_date",
    "scan_location",
    "responsible",
    "identifier",
    "hash_sha256",
    "title",
    "document_type",
    "author",
    "subject",
)
"""Os oito metadados mínimos do Anexo II (o hash conta como um) na ordem do Decreto."""
SOURCE_LABEL = {
    "file_tag": "do arquivo",
    "file_mtime": "data do arquivo",
    "profile": "do perfil",
    "generated": "gerado pelo programa",
    "computed": "calculado",
    "ocr": "lido por OCR",
    "reviewer": "informado pelo revisor",
    "unavailable": "não disponível",
}
"""Origem de cada valor, como aparece no arquivo de metadados."""
HASHES_FILE = "hashes.sha256"
METADATA_FOLDER = "metadados"
SCHEMA_VERSION = "1"
QA_NS = "urn:qa-digitalizacao:metadados:1"


def exif_datetime(when: datetime) -> str:
    """``AAAA:MM:DD hh:mm:ss`` em UTC, o formato da tag TIFF DateTime."""
    return when.astimezone(UTC).strftime("%Y:%m:%d %H:%M:%S")


def ascii_text(text: str) -> str:
    """Texto em ASCII de 7 bits, como a especificação TIFF pede para tags de texto."""
    folded = unicodedata.normalize("NFKD", text.replace("°", " graus"))
    return folded.encode("ascii", "ignore").decode("ascii")


def software_tag(original: str | None, engine_version: str, changes: Sequence[str]) -> str:
    """Tag Software: a do original seguida do que o programa fez com a página.

    A parte do programa vai sem acentos (ASCII); o texto completo fica no XMP e no
    arquivo de metadados do processo.
    """
    done = f"corrigida: {'; '.join(changes)}" if changes else "sem correção de imagem"
    ours = ascii_text(f"qa-digitalizacao {engine_version} ({done})")
    return f"{original}; {ours}" if original else ours


def page_changes(item: Mapping[str, Any]) -> list[str]:
    """Correções de imagem e mudança de posição de uma página do plano, em texto."""
    return [str(change["text"]) for change in item["changes"]]


def _field_view(field: Mapping[str, Any]) -> dict[str, Any]:
    source = str(field["source"])
    return {
        "name": field["name"],
        "value": field.get("value"),
        "source": source,
        "source_label": SOURCE_LABEL.get(source, source),
        "confidence": field["confidence"],
        "confirmed": bool(field.get("confirmed", False)),
        "required_by_decree": bool(field.get("required_by_decree", False)),
    }


def decree_values(fields: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Valor de cada campo do Decreto que tem valor."""
    return {
        f["name"]: f["value"]
        for f in fields
        if f["name"] in DECREE_FIELDS and f.get("value") not in (None, "")
    }


def _li(values: Iterable[Any]) -> str:
    return "".join(f"<rdf:li>{escape(str(v))}</rdf:li>" for v in values)


def xmp_packet(
    fields: Iterable[Mapping[str, Any]],
    *,
    source_file: str,
    source_sha256: str,
    changes: Sequence[str],
    engine_version: str,
    corrected_at: datetime | None,
    exif: Mapping[str, str],
) -> bytes:
    """XMP da página com os campos do Decreto (Dublin Core onde há equivalente).

    Os campos sem equivalente (local, responsável, hash do original) e as correções
    vão no espaço de nomes do programa.
    """
    values = decree_values(fields)
    parts: list[str] = []
    if "scan_date" in values:
        parts.append(f"<xmp:CreateDate>{escape(str(values['scan_date']))}</xmp:CreateDate>")
    if corrected_at is not None:
        parts.append(f"<xmp:ModifyDate>{corrected_at.astimezone(UTC).isoformat()}</xmp:ModifyDate>")
    parts.append(f"<xmp:CreatorTool>qa-digitalizacao {escape(engine_version)}</xmp:CreatorTool>")
    if "identifier" in values:
        parts.append(f"<dc:identifier>{escape(str(values['identifier']))}</dc:identifier>")
    if "title" in values:
        parts.append(
            '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">'
            f"{escape(str(values['title']))}</rdf:li></rdf:Alt></dc:title>"
        )
    if "author" in values:
        parts.append(f"<dc:creator><rdf:Seq>{_li([values['author']])}</rdf:Seq></dc:creator>")
    if "subject" in values:
        parts.append(f"<dc:subject><rdf:Bag>{_li([values['subject']])}</rdf:Bag></dc:subject>")
    if "document_type" in values:
        parts.append(f"<dc:type><rdf:Bag>{_li([values['document_type']])}</rdf:Bag></dc:type>")
    for name, tag in (("scan_location", "scanLocation"), ("responsible", "responsible")):
        if name in values:
            parts.append(f"<qa:{tag}>{escape(str(values[name]))}</qa:{tag}>")
    parts.append(f"<qa:sourceFile>{escape(source_file)}</qa:sourceFile>")
    parts.append(f"<qa:sourceSha256>{escape(source_sha256)}</qa:sourceSha256>")
    if changes:
        parts.append(f"<qa:corrections><rdf:Seq>{_li(changes)}</rdf:Seq></qa:corrections>")
    for name, value in exif.items():
        prefix = "exifEX" if name in {"BodySerialNumber", "ImageUniqueID"} else "exif"
        parts.append(f"<{prefix}:{name}>{escape(value)}</{prefix}:{name}>")
    body = "\n    ".join(parts)
    packet = (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description rdf:about=""\n'
        '    xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
        '    xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n'
        '    xmlns:exif="http://ns.adobe.com/exif/1.0/"\n'
        '    xmlns:exifEX="http://cipa.jp/exif/1.0/"\n'
        f'    xmlns:qa="{QA_NS}">\n'
        f"    {body}\n"
        "  </rdf:Description>\n"
        " </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    )
    return packet.encode("utf-8")


def metadata_file_name(document: Mapping[str, Any]) -> str:
    """``metadados/<pasta do processo>.json`` (barras viram hífen)."""
    base = str(document["folder"] or document["name"]).strip("/").replace("/", "-")
    cleaned = "".join("_" if c in '<>:"\\|?*' or ord(c) < 32 else c for c in base).strip(". ")
    return f"{METADATA_FOLDER}/{cleaned or 'lote'}.json"


def document_metadata_file(
    document: Mapping[str, Any],
    fields: Sequence[Mapping[str, Any]],
    files: Sequence[Mapping[str, Any]],
    *,
    batch_id: str,
    batch_name: str,
    generated_at: str,
    engine_version: str,
    embedded_xmp: bool,
) -> dict[str, Any]:
    """Arquivo de metadados de um processo (``delivery-metadata.schema.json``)."""
    decree = [_field_view(f) for f in fields if f["name"] in DECREE_FIELDS]
    decree.sort(key=lambda f: DECREE_FIELDS.index(f["name"]))
    technical = [_field_view(f) for f in fields if f["name"] not in DECREE_FIELDS]
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "batch_name": batch_name,
        "document": document["name"],
        "folder": document["folder"],
        "generated_at": generated_at,
        "engine_version": engine_version,
        "embedded_xmp": embedded_xmp,
        "decree": decree,
        "technical": technical,
        "files": list(files),
    }


def hashes_text(entries: Iterable[tuple[str, str]]) -> str:
    """``hashes.sha256`` no formato do ``sha256sum``: ``<hash>  <arquivo>`` por linha."""
    return "".join(f"{sha}  {path}\n" for path, sha in sorted(entries))
