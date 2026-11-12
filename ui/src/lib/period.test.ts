import { describe, expect, it } from "vitest";
import { periodLabel, periodRange } from "./period";

const ref = new Date(2026, 10, 12, 15, 30); // quinta-feira, 12/11/2026

describe("períodos da Gestão", () => {
  it("dia", () => {
    const p = periodRange("day", ref);
    expect([p.since.getDate(), p.until.getDate()]).toEqual([12, 13]);
    expect(periodRange("day", ref, -1).since.getDate()).toBe(11);
  });
  it("semana de segunda a domingo", () => {
    const p = periodRange("week", ref);
    expect([p.since.getDay(), p.since.getDate(), p.until.getDate()]).toEqual([1, 9, 16]);
    expect(periodLabel("week", p)).toBe("09/11 a 15/11/2026");
  });
  it("mês, inclusive a virada do ano", () => {
    const p = periodRange("month", ref, 1);
    expect([p.since.getMonth(), p.until.getFullYear(), p.until.getMonth()]).toEqual([11, 2027, 0]);
    expect(periodLabel("month", periodRange("month", ref))).toBe("novembro de 2026");
  });
});
