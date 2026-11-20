"""Confere o relatório do motor contra o gabarito da caixa de regressão.

Mede, por problema inserido, quantos o motor achou; nas duplicatas, separa "par achado" de
"cópia certa marcada"; conta avisos fora do gabarito, correções automáticas em página limpa,
lacunas de numeração maiores que o documento, "fora de ordem" (a caixa nunca embaralha
páginas) e as folhas perdidas declaradas no ``manifest.csv``. Com ``--tempos`` (saída do
``time_pages.py``) inclui tempo por página e o ângulo de inclinação medido. Com
``--baseline`` compara e reprova pelas regras de ``docs/testes/caixa-de-regressao.md``.

Uso::

    python3 tools/bench_box/score_box.py --gabarito <dir_gabarito> --report <saida>/report.json \
        [--tempos tempos.json] [--baseline tools/bench_box/baseline-1.2.0.json] \
        [--json resultado.json] [--md resultado.md]

``<dir_gabarito>`` é a pasta com ``gabarito_caixa_teste.csv`` e ``paginas_perdidas.csv``.
Sai com código 1 quando a comparação com a base reprova.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

RULE_OF = {
    "rotacao": "orientation",
    "inclinacao": "skew",
    "desfoque": "blur",
    "exposicao_escura": "exposure",
    "exposicao_clara": "exposure",
    "borda_preta": "black_borders",
    "baixa_resolucao": "low_resolution",
    "branca": "blank_page",
    "branca_verso": "blank_page",
    "duplicata": "duplicate_page",
    "corrompido": "corrupted_file",
}
"""Problema do gabarito → regra do motor que deve apontá-lo."""

CO_OCCURRENCE = {"desfoque": {"exposure"}}
"""Aviso a mais aceito por ser consequência do problema (desfoque derruba o contraste)."""

NUMBERING_RULES = {"numbering_review"}
"""Avisos de numeração: as folhas do RVL-CDIP não têm número de folha; ficam fora da conta."""

GAP = re.compile(r"Faltam fls\. (\d+) a (\d+)")


def load_truth(folder: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Gabarito por página e processos com folha perdida (``processo`` → faltando)."""
    with open(folder / "gabarito_caixa_teste.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    lost: dict[str, int] = {}
    lost_path = folder / "paginas_perdidas.csv"
    if lost_path.is_file():
        with open(lost_path, encoding="utf-8") as fh:
            lost = {r["processo"]: int(r["faltando"]) for r in csv.DictReader(fh)}
    return rows, lost


def key(row: dict[str, str]) -> str:
    """Caminho relativo da página no lote."""
    return f"processo {row['processo']}/{row['arquivo']}"


def problems(row: dict[str, str]) -> list[str]:
    """Problemas inseridos na página (vazio se limpa)."""
    return [p for p in row["problemas"].split("+") if p != "nenhum"]


def score(
    truth: list[dict[str, str]],
    lost: dict[str, int],
    report: dict[str, Any],
    tempos: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resultado do motor contra o gabarito, em formato de máquina."""
    pages = {p["id"]: p for p in report["pages"]}
    docs = {d["id"]: d for d in report["documents"]}
    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    doc_findings: list[dict[str, Any]] = []
    for f in report["findings"]:
        if f["target"]["kind"] == "page":
            by_page[pages[f["target"]["id"]]["source_file"]].append(f)
        else:
            doc_findings.append(f)
    truth_by_key = {key(r): r for r in truth}

    found: Counter[str] = Counter()
    total: Counter[str] = Counter()
    missed: dict[str, list[str]] = defaultdict(list)
    for r in truth:
        rules = {f["rule"] for f in by_page.get(key(r), [])}
        for p in problems(r):
            if p == "duplicata":
                continue
            total[p] += 1
            if RULE_OF[p] in rules:
                found[p] += 1
            else:
                missed[p].append(key(r))

    # Duplicatas: par achado (qualquer uma das duas marcada) e cópia certa (a do gabarito).
    pairs_found = right_copy = 0
    dup_pairs = []
    for r in truth:
        if r["tipo_folha"] != "duplicata":
            continue
        source = re.search(r"duplicata_de=(\S+?\.png)", r["detalhes"])
        src_key = f"processo {r['processo']}/{source.group(1)}" if source else ""
        copy_flag = any(f["rule"] == "duplicate_page" for f in by_page.get(key(r), []))
        src_flag = any(f["rule"] == "duplicate_page" for f in by_page.get(src_key, []))
        pairs_found += copy_flag or src_flag
        right_copy += copy_flag
        dup_pairs.append(
            {
                "copy": key(r),
                "source": src_key,
                "copy_flagged": copy_flag,
                "source_flagged": src_flag,
            }
        )
        if not (copy_flag or src_flag):
            missed["duplicata"].append(key(r))
    total["duplicata"] = len(dup_pairs)
    found["duplicata"] = pairs_found
    dup_sources = {d["source"] for d in dup_pairs}

    # Avisos fora do gabarito.
    false_flags: list[dict[str, Any]] = []
    auto_on_clean: list[dict[str, Any]] = []
    clean_flags = 0
    for page_key, findings in by_page.items():
        r = truth_by_key.get(page_key)
        if r is None:
            continue
        expected = {RULE_OF[p] for p in problems(r)}
        accepted = set().union(*(CO_OCCURRENCE.get(p, set()) for p in problems(r)))
        for f in findings:
            rule = f["rule"]
            if rule in expected or rule in NUMBERING_RULES:
                continue
            if rule == "duplicate_page" and page_key in dup_sources:
                continue  # par achado com a cópia errada: contado nas duplicatas
            if rule in accepted:
                continue
            entry = {
                "page": page_key,
                "rule": rule,
                "inserted": r["problemas"],
                "measure": f.get("measure"),
                "confidence": f.get("confidence"),
            }
            false_flags.append(entry)
            if not problems(r):
                clean_flags += 1
                corr = f.get("correction") or {}
                if corr.get("kind") == "automatic" and not (corr.get("params") or {}).get("review"):
                    auto_on_clean.append(entry)

    # Documento: lacunas absurdas, fora de ordem e folhas perdidas pelo manifest.csv.
    sizes = {d["name"]: len(d["page_ids"]) for d in docs.values()}
    absurd, out_of_order, lost_found = [], [], set()
    for f in doc_findings:
        name = docs[f["target"]["id"]]["name"]
        if f["rule"] == "missing_page":
            m = GAP.search(f["message"])
            if m and int(m.group(2)) - int(m.group(1)) + 1 > sizes.get(name, 0):
                absurd.append({"document": name, "message": f["message"]})
            if "Contagem declarada" in f["message"]:
                lost_found.add(name.split()[-1])
        elif f["rule"] == "out_of_order":
            out_of_order.append(name)

    per_problem = {p: {"found": found[p], "total": total[p]} for p in sorted(total)}
    hit = sum(found.values())
    all_ = sum(total.values())
    result: dict[str, Any] = {
        "engine_version": report["batch"].get("engine_version"),
        "pages": len(report["pages"]),
        "problems": per_problem,
        "total": {"found": hit, "total": all_, "ratio": round(hit / all_, 4) if all_ else None},
        "duplicates": {
            "pairs": len(dup_pairs),
            "pairs_found": pairs_found,
            "right_copy": right_copy,
            "detail": dup_pairs,
        },
        "missed": {k: sorted(v) for k, v in sorted(missed.items())},
        "false_flags": {
            "count": len(false_flags),
            "by_rule": dict(Counter(f["rule"] for f in false_flags)),
            "detail": false_flags,
        },
        "clean_page_flags": clean_flags,
        "auto_corrections_on_clean": auto_on_clean,
        "absurd_gaps": absurd,
        "out_of_order": out_of_order,
        "lost_pages": {"declared": sorted(lost), "found": sorted(lost_found)},
    }
    if tempos:
        secs = [p["seconds"] for p in tempos["pages"][1:]]
        q = sorted(secs)
        result["timing"] = {
            "total_serial_s": tempos["total_seconds"],
            "first_page_s": tempos["pages"][0]["seconds"] if tempos["pages"] else None,
            "median_s": round(statistics.median(q), 4) if q else None,
            "p95_s": round(q[int(0.95 * (len(q) - 1))], 4) if q else None,
            "max_s": round(max(q), 4) if q else None,
        }
        result["skew_deg"] = {p["file"]: p["skew_deg"] for p in tempos["pages"]}
    return result


def duplicate_calibration(box: Path, truth: list[dict[str, str]], top: int = 10) -> dict[str, Any]:
    """Semelhança alinhada e diferença de tinta dos pares verdadeiros e dos falsos mais parecidos.

    Usa as mesmas funções do motor (``duplicate_page``); precisa rodar com o ambiente do
    motor (``uv run --project engine``). Serve para escolher ``min_similarity`` e
    ``max_ink_difference``: o limite fica no vão entre os dois grupos.
    """
    from qa_engine.adapters.images import FileImageSource
    from qa_engine.application.analyze import ANALYSIS_DPI
    from qa_engine.detectors import duplicate_page as dp
    from qa_engine.detectors.features import compute_features
    from qa_engine.detectors.registry import params_for

    params = params_for(dp.ID, None)
    prints: dict[str, Any] = {}
    for r in truth:
        if r["tipo_folha"] == "corrompido":
            continue
        try:
            gray = FileImageSource().load(box / key(r), 0, ANALYSIS_DPI).gray
        except Exception:
            continue
        feat = compute_features(gray)
        view, ink = dp.views(gray, feat.ink)
        prints[key(r)] = (
            dp.dhash(gray),
            dp._unit(dp.thumbnail(gray)),
            dp._decode(view),
            dp._decode(ink) > 0,
        )
    true_pairs = set()
    for r in truth:
        m = re.search(r"duplicata_de=(\S+?\.png)", r["detalhes"])
        if r["tipo_folha"] == "duplicata" and m:
            true_pairs.add(tuple(sorted((key(r), f"processo {r['processo']}/{m.group(1)}"))))
    keys = list(prints)
    rows = []
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            pa, pb = prints[a], prints[b]
            if (pa[0] ^ pb[0]).bit_count() > int(params["max_hash_distance"]):
                continue
            if float(pa[1] @ pb[1]) < float(params["candidate_min_similarity"]):
                continue
            sim, ink = dp.aligned_comparison(pa[2], pa[3], pb[2], pb[3])
            rows.append(
                {
                    "pair": [a, b],
                    "true": (a, b) in true_pairs,
                    "similarity": round(sim, 4),
                    "ink_difference": round(ink, 4),
                }
            )
    true_rows = sorted((r for r in rows if r["true"]), key=lambda r: r["similarity"])
    false_rows = sorted((r for r in rows if not r["true"]), key=lambda r: -r["similarity"])
    return {"true": true_rows, "closest_false": false_rows[:top], "candidates": len(rows)}


def compare(result: dict[str, Any], base: dict[str, Any], skew_tol: float = 0.05) -> list[str]:
    """Motivos de reprovação contra a base (vazio = aprovado)."""
    fails: list[str] = []
    for p, v in base["problems"].items():
        now = result["problems"].get(p, {"found": 0})["found"]
        if now < v["found"]:
            fails.append(f"{p}: {now} contra {v['found']} da base")
    if result["duplicates"]["right_copy"] < base["duplicates"]["right_copy"]:
        fails.append("duplicata: menos cópias certas que a base")
    if result["false_flags"]["count"] > base["false_flags"]["count"] + 5:
        fails.append(
            f"avisos falsos: {result['false_flags']['count']} contra "
            f"{base['false_flags']['count']} da base (+5 no máximo)"
        )
    if len(result["auto_corrections_on_clean"]) > len(base["auto_corrections_on_clean"]):
        fails.append("correção automática nova em página limpa")
    if len(result["absurd_gaps"]) > len(base["absurd_gaps"]):
        fails.append("lacuna maior que o documento nova")
    t, bt = result.get("timing"), base.get("timing")
    if t and bt and t["median_s"] > bt["median_s"] * 1.10:
        fails.append(f"mediana de tempo {t['median_s']} s contra {bt['median_s']} s (+10%)")
    return fails


def skew_drift(result: dict[str, Any], base: dict[str, Any], tol: float = 0.05) -> list[str]:
    """Páginas cujo ângulo de inclinação medido mudou mais que ``tol`` graus."""
    a, b = result.get("skew_deg") or {}, base.get("skew_deg") or {}
    out = []
    for page, old in b.items():
        new = a.get(page)
        if old is None or new is None:
            if (old is None) != (new is None):
                out.append(f"{page}: {old} → {new}")
        elif abs(new - old) > tol:
            out.append(f"{page}: {old}° → {new}°")
    return out


def markdown(result: dict[str, Any], fails: list[str] | None) -> str:
    """Resumo legível do resultado."""
    lines = [f"# Caixa de regressão — motor {result['engine_version']}", ""]
    t = result["total"]
    lines += [
        f"Achados: **{t['found']} / {t['total']}** ({t['ratio']:.1%}).",
        "",
        "| Problema | Achado / inserido |",
        "| --- | --- |",
    ]
    for p, v in result["problems"].items():
        lines.append(f"| {p} | {v['found']} / {v['total']} |")
    d = result["duplicates"]
    lines += [
        "",
        f"Duplicatas: {d['pairs_found']} de {d['pairs']} pares achados, "
        f"{d['right_copy']} com a cópia certa marcada.",
        "",
        f"Avisos fora do gabarito: {result['false_flags']['count']} "
        f"({result['false_flags']['by_rule']}); em página limpa: {result['clean_page_flags']}.",
        f"Correções automáticas em página limpa: {len(result['auto_corrections_on_clean'])}.",
        f"Lacunas maiores que o documento: {len(result['absurd_gaps'])}. "
        f"Fora de ordem (falsos): {len(result['out_of_order'])}.",
        f"Folhas perdidas pelo manifest: {len(result['lost_pages']['found'])} de "
        f"{len(result['lost_pages']['declared'])}.",
    ]
    if "timing" in result:
        tm = result["timing"]
        lines += [
            "",
            f"Tempo em série: mediana {tm['median_s']} s, p95 {tm['p95_s']} s, "
            f"máximo {tm['max_s']} s por página; total {tm['total_serial_s']} s.",
        ]
    lines += ["", "## Escaparam", ""]
    for p, keys in result["missed"].items():
        lines.append(f"- {p}: {', '.join(keys)}")
    if fails is not None:
        lines += ["", "## Comparação com a base", ""]
        lines += [f"- REPROVA: {f}" for f in fails] or ["- Aprovado."]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Ponto de entrada."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gabarito", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--tempos", type=Path)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument(
        "--calibrar-duplicata",
        type=Path,
        metavar="CAIXA",
        help="pasta da caixa: imprime a semelhança alinhada dos pares (precisa do motor)",
    )
    ap.add_argument(
        "--check-skew",
        action="store_true",
        help="reprova se o ângulo de inclinação mudar mais de 0,05° em alguma página",
    )
    args = ap.parse_args()
    truth, lost = load_truth(args.gabarito)
    report = json.loads(args.report.read_text("utf-8"))
    tempos = json.loads(args.tempos.read_text("utf-8")) if args.tempos else None
    result = score(truth, lost, report, tempos)
    fails = None
    if args.baseline:
        base = json.loads(args.baseline.read_text("utf-8"))
        fails = compare(result, base)
        drift = skew_drift(result, base)
        result["skew_drift"] = drift
        if args.check_skew and drift:
            fails.append(f"inclinação mudou em {len(drift)} páginas: {drift[:5]}")
    if args.calibrar_duplicata:
        cal = duplicate_calibration(args.calibrar_duplicata, truth)
        result["duplicate_calibration"] = cal
        sims = [(r["similarity"], r["ink_difference"]) for r in cal["true"]]
        print(f"Duplicata, {cal['candidates']} candidatos. Verdadeiros (semelhança, tinta): {sims}")
        print(
            "Falsos mais parecidos:",
            [(r["similarity"], r["ink_difference"]) for r in cal["closest_false"]],
        )
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", "utf-8")
    text = markdown(result, fails)
    if args.md:
        args.md.write_text(text, "utf-8")
    print(text)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
