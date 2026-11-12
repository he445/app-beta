import { describe, expect, it } from "vitest";
import type { Numbering } from "../api/types";
import { dropAt, firstToType, inverse, moveItem, needsTyping, nextToType, sequenceKey, typedChange, workingOrder } from "./sequence";

const n = (state: Numbering["state"], value: string | null = null, typed?: string): Numbering => ({
  state,
  value,
  confidence: 0.5,
  previous: [],
  ...(typed === undefined ? {} : { typed }),
});

describe("ordem", () => {
  it("usa a ordem manual quando houver", () => {
    expect(workingOrder({ page_ids: ["a", "b"] })).toEqual(["a", "b"]);
    expect(workingOrder({ page_ids: ["a", "b"], manual_order: { page_ids: ["b", "a"], reviewer: "g", decided_at: "x" } })).toEqual(["b", "a"]);
  });
  it("move com Alt + setas sem sair da faixa", () => {
    expect(moveItem(["a", "b", "c"], 2, -1)).toEqual(["a", "c", "b"]);
    expect(moveItem(["a", "b", "c"], 0, -1)).toEqual(["a", "b", "c"]);
    expect(moveItem(["a", "b", "c"], 0, 1)).toEqual(["b", "a", "c"]);
  });
  it("arrastar solta antes da página alvo", () => {
    expect(dropAt(["a", "b", "c", "d"], "d", 1)).toEqual(["a", "d", "b", "c"]);
    expect(dropAt(["a", "b", "c", "d"], "a", 3)).toEqual(["b", "c", "a", "d"]);
    expect(dropAt(["a", "b", "c", "d"], "a", 4)).toEqual(["b", "c", "d", "a"]);
    expect(dropAt(["a", "b"], "x", 0)).toEqual(["a", "b"]);
  });
});

describe("digitação rápida", () => {
  const order = ["a", "b", "c", "d"];
  const numbering = { a: n("read", "1"), b: n("ambiguous"), c: n("read", "3"), d: n("illegible") };
  it("começa na primeira dúvida e pula as lidas", () => {
    expect(firstToType(order, numbering)).toBe(1);
    expect(nextToType(order, numbering, 1)).toBe(3);
    expect(nextToType(order, numbering, 3)).toBeNull();
    expect(nextToType(order, { ...numbering, d: n("read", "4") }, 1)).toBe(2);
  });
  it("página já digitada não precisa mais do revisor", () => {
    expect(needsTyping(n("inferred", "2", "2"))).toBe(false);
    expect(needsTyping(n("absent"))).toBe(true);
    expect(needsTyping(undefined)).toBe(true);
  });
  it("só grava o que muda", () => {
    expect(typedChange(" 12 ", n("ambiguous"))).toBe("12");
    expect(typedChange("", n("ambiguous"))).toBeNull();
    expect(typedChange("1", n("read", "1"))).toBeNull();
    expect(typedChange("1", n("inferred", "1"))).toBe("1");
    expect(typedChange("2", n("read", "2", "2"))).toBeNull();
  });
});

describe("desfazer", () => {
  it("devolve os números e a ordem de antes", () => {
    const undo = inverse({ values: { a: "1", b: "2" }, order: ["b", "a"] }, { typed: { a: "9" }, manualOrder: undefined });
    expect(undo).toEqual({ values: { a: "9", b: null }, order: null });
    expect(inverse({ values: { a: "1" } }, { typed: {}, manualOrder: ["a"] })).toEqual({ values: { a: null } });
  });
  it("atalhos", () => {
    expect(sequenceKey({ key: "ArrowLeft", altKey: true })).toEqual({ type: "move", delta: -1 });
    expect(sequenceKey({ key: "ArrowRight" })).toBeNull();
    expect(sequenceKey({ key: "z", ctrlKey: true })).toEqual({ type: "undo" });
  });
});
