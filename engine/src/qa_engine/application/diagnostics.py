"""Diagnóstico: registro de erros sem conteúdo de documento, agrupado por assinatura.

Cada registro guarda data e hora, versão, computador, sistema, usuário, gravidade,
tipo do erro, pilha, tela ou rota e os identificadores do lote e da página. Nunca
guarda imagem nem texto lido; caminhos absolutos são mascarados. Erros iguais têm a
mesma assinatura: tipo + local no código + mensagem sem números variáveis.
"""

from __future__ import annotations

import hashlib
import io
import json
import platform
import re
import traceback
import uuid
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from qa_engine.adapters.logs import mask_paths

SEVERITIES = ("critical", "error", "warning")
ORIGINS = ("engine", "worker", "startup", "client")
_VARIABLE = re.compile(r"0x[0-9a-fA-F]+|[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}|\d+")
MAX_STACK = 20_000
MAX_MESSAGE = 1_000


def normalize_message(message: str) -> str:
    """Mensagem sem os pedaços que mudam a cada ocorrência (números, ids, endereços)."""
    return _VARIABLE.sub("#", mask_paths(message)).strip()


def signature(kind: str, where: str, message: str) -> str:
    """Assinatura que agrupa erros iguais."""
    text = f"{kind}\n{where}\n{normalize_message(message)}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def code_location(error: BaseException) -> str:
    """Último quadro da pilha dentro do programa (``arquivo:função``), sem caminho absoluto."""
    frames = traceback.extract_tb(error.__traceback__) if error.__traceback__ else []
    own = [f for f in frames if "qa_engine" in f.filename] or frames
    if not own:
        return "?"
    frame = own[-1]
    name = frame.filename.replace("\\", "/").split("qa_engine/")[-1]
    return f"{name}:{frame.name}"


def system_info(version: str, user: str | None) -> dict[str, Any]:
    """Versão do programa, computador, sistema e usuário."""
    return {
        "version": version,
        "machine": platform.node() or "?",
        "os": f"{platform.system()} {platform.release()}".strip() or "?",
        "user": user,
    }


def record_from_exception(
    error: BaseException,
    *,
    origin: str,
    severity: str,
    where: str | None,
    version: str,
    user: str | None,
    batch_id: str | None = None,
    page_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Registro de diagnóstico de uma exceção do motor ou de um processo de análise."""
    kind = type(error).__name__
    location = code_location(error)
    message = mask_paths(str(error))[:MAX_MESSAGE]
    stack = mask_paths("".join(traceback.format_exception(error)))[:MAX_STACK]
    return {
        "id": str(uuid.uuid4()),
        "signature": signature(kind, location, message),
        "at": (now or datetime.now(tz=UTC)).isoformat().replace("+00:00", "Z"),
        **system_info(version, user),
        "severity": severity,
        "origin": origin,
        "kind": kind,
        "location": location,
        "message": message,
        "stack": stack,
        "where": where,
        "batch_id": batch_id,
        "page_id": page_id,
    }


def record_from_client(
    body: Mapping[str, Any], *, version: str, user: str | None, now: datetime | None = None
) -> dict[str, Any]:
    """Registro de um erro da interface (``POST /diagnostics/client-errors``)."""
    kind = str(body.get("kind") or "Error")[:100]
    message = mask_paths(str(body.get("message") or ""))[:MAX_MESSAGE]
    stack = mask_paths(str(body.get("stack") or ""))[:MAX_STACK]
    first = next((line.strip() for line in stack.splitlines()[1:] if line.strip()), "")
    location = re.sub(r"https?://[^/]+/|\?.*|:\d+:\d+\)?$", "", first)[:200] or "?"
    return {
        "id": str(uuid.uuid4()),
        "signature": signature(kind, location, message),
        "at": (now or datetime.now(tz=UTC)).isoformat().replace("+00:00", "Z"),
        **system_info(version, user),
        "severity": "error",
        "origin": "client",
        "kind": kind,
        "location": location,
        "message": message,
        "stack": stack,
        "where": str(body.get("screen") or "")[:200] or None,
        "batch_id": body.get("batch_id"),
        "page_id": body.get("page_id"),
    }


def record_from_crash_file(text: str, name: str, version: str) -> dict[str, Any]:
    """Registro de um arquivo de queda da abertura (lido na abertura seguinte)."""
    lines = [line for line in text.splitlines() if line.strip()]
    last = lines[-1] if lines else "Erro"
    kind, _, message = last.partition(": ")
    stack = mask_paths(text)[:MAX_STACK]
    location = next(
        (
            line.strip().split("qa_engine")[-1]
            for line in reversed(lines)
            if line.strip().startswith("File") and "qa_engine" in line
        ),
        "?",
    )
    stamp = re.search(r"crash-(\d{8})-(\d{6})", name)
    at = (
        datetime.strptime("".join(stamp.groups()), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        if stamp
        else datetime.now(tz=UTC)
    )
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"crash/{name}")),
        "signature": signature(kind.strip(), location, message),
        "at": at.isoformat().replace("+00:00", "Z"),
        **system_info(version, None),
        "severity": "critical",
        "origin": "startup",
        "kind": kind.strip()[:100] or "Erro",
        "location": location[:200],
        "message": mask_paths(message)[:MAX_MESSAGE],
        "stack": stack,
        "where": "abertura do programa",
        "batch_id": None,
        "page_id": None,
    }


def _parse(at: str) -> datetime:
    return datetime.fromisoformat(at.replace("Z", "+00:00"))


def filtered(
    records: Iterable[Mapping[str, Any]], filters: Mapping[str, str | None]
) -> list[Mapping[str, Any]]:
    """Registros que passam nos filtros de versão, máquina, gravidade e origem."""
    result = []
    for r in records:
        if any(
            filters.get(k) and r.get(k) != filters[k]
            for k in ("version", "machine", "severity", "origin")
        ):
            continue
        result.append(r)
    return result


def groups(
    records: Iterable[Mapping[str, Any]], resolved: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Erros agrupados por assinatura, do mais recente ao mais antigo.

    Um grupo resolvido volta a ficar aberto se ocorrer de novo depois da resolução.
    """
    by_sig: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in records:
        by_sig[r["signature"]].append(r)
    result = []
    for sig, items in by_sig.items():
        items = sorted(items, key=lambda r: r["at"])
        last = items[-1]
        fix = resolved.get(sig)
        status = "resolved" if fix and fix["resolved_at"] >= last["at"] else "open"
        result.append(
            {
                "signature": sig,
                "kind": last["kind"],
                "message": normalize_message(last["message"]),
                "location": last["location"],
                "severity": max(items, key=lambda r: SEVERITIES[::-1].index(r["severity"]))[
                    "severity"
                ],
                "origin": last["origin"],
                "count": len(items),
                "machines": sorted({r["machine"] for r in items}),
                "versions": sorted({r["version"] for r in items}),
                "first_at": items[0]["at"],
                "last_at": last["at"],
                "status": status,
                "resolved_by": fix["resolved_by"] if fix and status == "resolved" else None,
            }
        )
    return sorted(result, key=lambda g: g["last_at"], reverse=True)


def summary(
    records: Sequence[Mapping[str, Any]],
    grouped: Sequence[Mapping[str, Any]],
    now: datetime,
    days: int = 30,
) -> dict[str, Any]:
    """Cartões do topo e erros por dia, por gravidade."""
    day0 = (now - timedelta(days=days - 1)).date()
    per_day: dict[str, Counter[str]] = {
        (day0 + timedelta(days=i)).isoformat(): Counter() for i in range(days)
    }
    for r in records:
        day = _parse(r["at"]).date().isoformat()
        if day in per_day:
            per_day[day][r["severity"]] += 1
    return {
        "last_24h": sum(_parse(r["at"]) >= now - timedelta(hours=24) for r in records),
        "last_7d": sum(_parse(r["at"]) >= now - timedelta(days=7) for r in records),
        "machines": len(
            {r["machine"] for r in records if _parse(r["at"]) >= now - timedelta(days=7)}
        ),
        "open": sum(g["status"] == "open" for g in grouped),
        "per_day": [
            {"day": day, **{s: counts.get(s, 0) for s in SEVERITIES}}
            for day, counts in per_day.items()
        ],
    }


def export_package(
    records: Sequence[Mapping[str, Any]],
    grouped: Sequence[Mapping[str, Any]],
    settings_view: Mapping[str, Any],
    version: str,
    now: datetime,
) -> bytes:
    """Zip para anexar num chamado: registros, grupos, versão e configuração sem segredos."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "LEIA-ME.txt", f"Diagnóstico do QA {version}, exportado em {now.isoformat()}.\n"
        )
        archive.writestr(
            "versao.json", json.dumps({"version": version, **system_info(version, None)})
        )
        archive.writestr("grupos.json", json.dumps(list(grouped), ensure_ascii=False, indent=2))
        archive.writestr(
            "registros.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
        )
        archive.writestr(
            "configuracao.json", json.dumps(settings_view, ensure_ascii=False, indent=2)
        )
    return buffer.getvalue()
