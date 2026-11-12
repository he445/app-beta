import { describe, expect, it } from "vitest";
import { SHORTCUT_GROUPS, isHelpKey } from "./keys";

describe("tela de atalhos", () => {
  it("abre com ? e não com outra combinação", () => {
    expect(isHelpKey({ key: "?" })).toBe(true);
    expect(isHelpKey({ key: "?", ctrlKey: true })).toBe(false);
    expect(isHelpKey({ key: "/" })).toBe(false);
  });
  it("cobre revisão, sequência e a própria tecla", () => {
    const titles = SHORTCUT_GROUPS.map((g) => g.title);
    expect(titles).toEqual(expect.arrayContaining(["Revisão", "Sequência", "Em qualquer tela"]));
    const all = SHORTCUT_GROUPS.flatMap((g) => g.keys.map(([k]) => k));
    expect(all).toEqual(expect.arrayContaining(["Q / E", "Alt + ← →", "?"]));
  });
});
