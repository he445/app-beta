import { describe, expect, it } from "vitest";
import { latestByBox } from "./BoxReportsCard";

const item = (id: string, box: string, version: number) => ({ id, report: { box, version } }) as never;

describe("relatórios por caixa", () => {
  it("mostra só a versão mais nova de cada caixa, em ordem de caixa", () => {
    const out = latestByBox([item("a", "CX10", 1), item("b", "CX2", 1), item("c", "CX10", 2)]);
    expect(out.map((i: { id: string }) => i.id)).toEqual(["b", "c"]);
  });
});
