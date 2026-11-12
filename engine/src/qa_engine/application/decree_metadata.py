"""Metadados do Decreto 10.278/2020 no lote corrigido (``metadados-no-lote-corrigido.md``).

Dois lugares, até a coordenação confirmar o formato que o cliente exige:

- **no TIFF:** as tags descritivas do original preservadas; ``Software`` e ``DateTime``
  dizem que a página passou por correção, e qual; um pacote XMP traz os campos do
  Decreto com a origem de cada valor e a data original;
- **por processo:** ``metadados.json`` com os campos, a origem e o SHA-256 de cada
  arquivo entregue.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape

PROCESS_FILE = "metadados.json"
NAMESPACE = "https://qa-digitalizacao.local/ns/decreto-10278/1.0/"
SOURCE_LABEL = {
    "file_tag": "do arquivo",
    "file_mtime": "data do arquivo",
    "profile": "do perfil",
    "generated": "gerado",
    "computed": "calculado",
    "ocr": "lido na página",
    "reviewer": "informado pelo revisor",
    "unavailable": "indisponível",
}


def ascii_text(text: str) -> str:
    """Texto para tag ASCII do TIFF: sem acentos (o XMP leva o texto completo)."""
    plain = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in plain if not unicodedata.combining(c) and ord(c) < 128)


def software_tag(engine_version: str, changes: Sequence[str]) -> str:
    """``Software``: o programa e o que mudou na página."""
    what = "; ".join(changes) if changes else "sem alteração da imagem"
    return ascii_text(f"qa-digitalizacao {engine_version} (lote corrigido: {what})")


def tiff_datetime(when: datetime) -> str:
    """``DateTime`` no formato do TIFF (``AAAA:MM:DD HH:MM:SS``)."""
    return when.strftime("%Y:%m:%d %H:%M:%S")


def page_tags(
    original: Mapping[str, Any], engine_version: str, changes: Sequence[str], when: datetime
) -> dict[str, str]:
    """Tags da página corrigida: as descritivas do original, mais software e data da correção."""
    tags = {k: ascii_text(str(v)) for k, v in original.items() if v not in (None, "")}
    tags["software"] = software_tag(engine_version, changes)
    tags["datetime"] = tiff_datetime(when)
    return tags


def xmp_packet(
    fields: Sequence[Mapping[str, Any]],
    changes: Sequence[str],
    original_datetime: str | None,
    engine_version: str,
    when: datetime,
) -> bytes:
    """Pacote XMP com os campos do Decreto (valor e origem), as correções e a data original."""

    def text(value: Any) -> str:
        return escape("" if value is None else str(value))

    items = "".join(
        '<rdf:li rdf:parseType="Resource">'
        f"<qa:campo>{text(f['name'])}</qa:campo>"
        f"<qa:valor>{text(f.get('value'))}</qa:valor>"
        f"<qa:origem>{text(f.get('source'))}</qa:origem>"
        f"<qa:confirmado>{'true' if f.get('confirmed') else 'false'}</qa:confirmado>"
        "</rdf:li>"
        for f in fields
    )
    fixes = "".join(f"<rdf:li>{text(c)}</rdf:li>" for c in changes)
    original = (
        f"<qa:dataOriginal>{text(original_datetime)}</qa:dataOriginal>" if original_datetime else ""
    )
    body = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
        f' xmlns:qa="{NAMESPACE}">'
        f"<xmp:CreatorTool>qa-digitalizacao {text(engine_version)}</xmp:CreatorTool>"
        f"<xmp:ModifyDate>{when.isoformat(timespec='seconds')}</xmp:ModifyDate>"
        f"{original}"
        f"<qa:campos><rdf:Bag>{items}</rdf:Bag></qa:campos>"
        f"<qa:correcoes><rdf:Seq>{fixes}</rdf:Seq></qa:correcoes>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>' + body + '<?xpacket end="w"?>'
    ).encode("utf-8")


def process_metadata(
    document: Mapping[str, Any],
    fields: Sequence[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """``metadados.json`` de um processo (``process-metadata.schema.json``).

    Args:
        document: documento do plano do lote corrigido, com o SHA-256 de cada página gravada.
        fields: metadados do documento (``metadata-field.schema.json``).
        generated_at: quando o lote corrigido foi gerado.
    """
    exported = sorted(
        (p for p in document["pages"] if p["status"] == "exported"),
        key=lambda p: p["new_position"],
    )
    return {
        "schema_version": "1",
        "document": document["name"],
        "generated_at": generated_at,
        "fields": [
            {
                "name": f["name"],
                "value": f.get("value"),
                "source": f.get("source", "unavailable"),
                "source_label": SOURCE_LABEL.get(str(f.get("source")), str(f.get("source"))),
                "required_by_decree": bool(f.get("required_by_decree")),
                "confirmed": bool(f.get("confirmed")),
            }
            for f in fields
        ],
        "files": [
            {
                "file": p["target_file"],
                "sha256": p["target_sha256"],
                "source_file": p["source_file"],
                "source_sha256": p["source_sha256"],
                "changes": [c["text"] for c in p.get("changes", [])],
            }
            for p in exported
        ],
    }
