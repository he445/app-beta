import { describe, expect, it } from "vitest";
import type { Analysis, Finding } from "../api/types";
import { parseSse } from "../api/sse";
import { csvObjects, parseCsv } from "./csv";
import { currentRotation, keyToAction, nextRotation } from "./keys";
import { buildQueue, clampIndex, replaceFinding } from "./queue";

function finding(id: string, severity: Finding["severity"], page: string, rule = "blur"): Finding {
  return {
    id,
    target: { kind: "page", id: page },
    rule,
    rule_version: "1.0.0",
    severity,
    measure: 0,
    threshold: 1,
    confidence: 1,
    message: "",
    correction: { kind: "physical", action: "rescan", description: "", params: {} },
  };
}

const page = (id: string, doc: string, index: number) => ({
  id, document_id: doc, index, source_file: `${id}.tif`, page_in_file: 0, width_px: 1,
  height_px: 1, dpi: 300, color_mode: "gray" as const, sha256: "0".repeat(64), loaded: true,
  station: null,
});

const report = {
  batch: {} as Analysis["batch"],
  documents: [
    { id: "d1", batch_id: "b", name: "A", page_ids: ["p1", "p2"], state: "red", proposed_order: [] },
    { id: "d2", batch_id: "b", name: "B", page_ids: ["p3"], state: "yellow", proposed_order: [] },
  ],
  pages: [page("p1", "d1", 0), page("p2", "d1", 1), page("p3", "d2", 0)],
  findings: [
    finding("f1", "low", "p1", "black_borders"),
    finding("f2", "critical", "p2"),
    finding("f3", "medium", "p3", "skew"),
    { ...finding("f4", "critical", "p1"), decision: { action: "approve", decided_at: "", reviewer: "x" } },
  ],
  metadata: {},
} as Analysis;

describe("fila de revisão", () => {
  it("ordena por severidade, documento e página", () => {
    const q = buildQueue(report, { severity: null, rule: null, pendingOnly: false });
    expect(q.map((i) => i.finding.id)).toEqual(["f4", "f2", "f3", "f1"]);
  });
  it("filtra pendentes, severidade e regra", () => {
    const base = { severity: null, rule: null, pendingOnly: true };
    expect(buildQueue(report, base).map((i) => i.finding.id)).toEqual(["f2", "f3", "f1"]);
    expect(buildQueue(report, { ...base, severity: "critical" }).map((i) => i.finding.id)).toEqual(["f2"]);
    expect(buildQueue(report, { ...base, rule: "skew" }).map((i) => i.finding.id)).toEqual(["f3"]);
  });
  it("mantém o índice dentro da fila e substitui a sinalização decidida", () => {
    expect(clampIndex(5, 3)).toBe(2);
    expect(clampIndex(-1, 3)).toBe(0);
    const decided = { ...finding("f2", "critical", "p2"), decision: { action: "reject" as const, decided_at: "", reviewer: "x" } };
    expect(replaceFinding(report, decided).findings[1]?.decision?.action).toBe("reject");
  });
});

describe("atalhos", () => {
  it("mapeia as teclas da revisão", () => {
    expect(keyToAction({ key: "a" })).toEqual({ type: "decide", action: "approve" });
    expect(keyToAction({ key: "C" })).toEqual({ type: "decide", action: "correct" });
    expect(keyToAction({ key: "r" })).toEqual({ type: "decide", action: "reject" });
    expect(keyToAction({ key: "o" })).toEqual({ type: "decide", action: "source_defect" });
    expect(keyToAction({ key: "ArrowRight" })).toEqual({ type: "move", delta: 1 });
    expect(keyToAction({ key: "ArrowLeft" })).toEqual({ type: "move", delta: -1 });
    expect(keyToAction({ key: " " })).toEqual({ type: "zoom" });
    expect(keyToAction({ key: "z", ctrlKey: true })).toEqual({ type: "undo" });
    expect(keyToAction({ key: "1" })).toEqual({ type: "filter", severity: "critical" });
    expect(keyToAction({ key: "4" })).toEqual({ type: "filter", severity: "low" });
    expect(keyToAction({ key: "5" })).toBeNull();
    expect(keyToAction({ key: "n" })).toEqual({ type: "numbering" });
    expect(keyToAction({ key: "a", ctrlKey: true })).toBeNull();
  });
});

describe("SSE e CSV", () => {
  it("separa eventos e guarda o resto incompleto", () => {
    const { events, rest } = parseSse('event: progress\ndata: {"a":1}\n\nevent: done\ndata: x\n\nevent: pro');
    expect(events).toEqual([{ event: "progress", data: '{"a":1}' }, { event: "done", data: "x" }]);
    expect(rest).toBe("event: pro");
  });
  it("lê campos com aspas, vírgulas e quebras de linha", () => {
    expect(parseCsv('a,b\n"x, y","diz ""oi""\nok"\n')).toEqual([["a", "b"], ["x, y", 'diz "oi"\nok']]);
    expect(csvObjects("station,box\nE3,CX1\n")).toEqual([{ station: "E3", box: "CX1" }]);
  });
});


describe("rotação pelo teclado", () => {
  it("Q, E e W giram 90° à esquerda, 90° à direita e 180°", () => {
    expect(keyToAction({ key: "e" })).toEqual({ type: "rotate", delta: 90 });
    expect(keyToAction({ key: "Q" })).toEqual({ type: "rotate", delta: 270 });
    expect(keyToAction({ key: "w" })).toEqual({ type: "rotate", delta: 180 });
  });

  it("o giro é somado ao que já está aplicado na cópia", () => {
    const findings = [
      { rule: "orientation", target: { kind: "page", id: "p" }, decision: { action: "correct" }, correction: { params: { angle_deg: 90 } } },
      { rule: "orientation", target: { kind: "page", id: "x" }, decision: { action: "approve" }, correction: { params: { angle_deg: 180 } } },
    ];
    expect(currentRotation(findings, "p")).toBe(90);
    expect(currentRotation(findings, "x")).toBe(0);
    expect(nextRotation(90, 270)).toBe(0);
    expect(nextRotation(270, 180)).toBe(90);
  });
});
