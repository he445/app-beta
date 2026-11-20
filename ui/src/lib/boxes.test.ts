import { describe, expect, it } from "vitest";
import type { Analysis } from "../api/types";
import { boxOf, boxesPending, pendingText } from "./boxes";

const finding = (id: string, target: string, severity: string, decided = false) =>
  ({
    id,
    rule: severity === "low" ? "blank_page" : "skew",
    severity,
    target: { kind: "page", id: target },
    ...(decided ? { decision: { action: "approve" } } : {}),
  }) as never;

const report = (findings: never[]) =>
  ({
    batch: { name: "lote" },
    documents: [
      { id: "d1", name: "CX1/proc-1", page_ids: ["p1"] },
      { id: "d2", name: "CX2/proc-2", page_ids: ["p2"] },
    ],
    findings,
  }) as unknown as Analysis;

describe("caixas pendentes", () => {
  it("a caixa é a primeira pasta; sem pasta, o lote", () => {
    expect(boxOf("CX1\\proc", "lote")).toBe("CX1");
    expect(boxOf("proc", "lote")).toBe("lote");
  });

  it("só médio ou acima sem decisão segura a caixa; baixa não", () => {
    const out = boxesPending(
      report([finding("a", "p1", "low"), finding("b", "p2", "high"), finding("c", "p2", "medium", true)]),
    );
    expect(out.map((b) => [b.box, b.pending.map((f) => f.id)])).toEqual([
      ["CX1", []],
      ["CX2", ["b"]],
    ]);
    expect(pendingText(out[1]!.pending)).toMatch(/^1 sinalização\(ões\) sem decisão \(1 /);
  });
});
