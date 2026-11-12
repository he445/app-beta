import { describe, expect, it } from "vitest";
import { SHORTCUTS, SHORTCUT_GROUPS, isHelpKey, keyToAction } from "./keys";

describe("tela de atalhos", () => {
  it("abre com ? fora de campos de texto", () => {
    expect(isHelpKey({ key: "?" })).toBe(true);
    expect(isHelpKey({ key: "?", ctrlKey: true })).toBe(false);
    expect(isHelpKey({ key: "/" })).toBe(false);
    expect(isHelpKey({ key: "?", target: null })).toBe(true);  // campo de texto: e2e desktop
  });

  it("? não decide nada na revisão", () => {
    expect(keyToAction({ key: "?" })).toBeNull();
  });

  it("lista todos os atalhos da revisão e das outras telas", () => {
    const review = SHORTCUT_GROUPS.find((g) => g.id === "review");
    expect(review?.items).toEqual(SHORTCUTS);
    expect(SHORTCUT_GROUPS.map((g) => g.id)).toEqual(["global", "review", "sequence", "zoom"]);
    const sequence = SHORTCUT_GROUPS.find((g) => g.id === "sequence")?.items.map(([k]) => k) ?? [];
    expect(sequence).toContain("Alt + ← →");
  });
});
