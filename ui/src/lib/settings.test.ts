import { describe, expect, it } from "vitest";
import type { Profile } from "../api/types";
import { formatComputerField, parseComputerField, parseParam, withRuleChange } from "./settings";

const profile: Profile = {
  id: "p",
  name: "P",
  organization: "O",
  stations: [{ id: "cg-e3", location: "E3", overrides: { black_borders: { params: { dark_level: 60 } } } }],
  detectors: { exposure: { enabled: true } },
};

describe("parseParam", () => {
  it("aceita número dentro da faixa, com vírgula", () => {
    expect(parseParam({ type: "number", minimum: 0, maximum: 1 }, "0,25")).toEqual({ value: 0.25, error: null });
  });
  it("recusa antes de mandar ao motor", () => {
    expect(parseParam({ type: "integer", minimum: 0 }, "-5").error).toBe("mínimo 0");
    expect(parseParam({ type: "integer" }, "2.5").error).toBe("digite um número inteiro");
    expect(parseParam({ type: "number", maximum: 255 }, "300").error).toBe("máximo 255");
    expect(parseParam({ type: "number" }, "abc").error).toBe("digite um número");
  });
});

describe("parseComputerField", () => {
  it("workers aceita auto ou inteiro ≥ 1", () => {
    expect(parseComputerField("workers", "auto").value).toBe("auto");
    expect(parseComputerField("workers", "").value).toBe("auto");
    expect(parseComputerField("workers", "3").value).toBe(3);
    expect(parseComputerField("workers", "0").error).toBe("mínimo 1");
  });
  it("pastas permitidas uma por linha, ida e volta", () => {
    const parsed = parseComputerField("allowed_roots", "\\\\srv\\a\n\n D:\\Lotes ");
    expect(parsed.value).toEqual(["\\\\srv\\a", "D:\\Lotes"]);
    expect(formatComputerField("allowed_roots", parsed.value)).toBe("\\\\srv\\a\nD:\\Lotes");
  });
  it("estação padrão vazia volta a nenhuma", () => {
    expect(parseComputerField("default_station", "").value).toBeNull();
    expect(parseComputerField("default_station", "Estação 3").error).toBe("identificador de estação");
  });
});

describe("withRuleChange", () => {
  it("muda o parâmetro só na estação e não altera o original", () => {
    const next = withRuleChange(profile, "cg-e3", "black_borders", { param: "dark_level", value: 55 });
    expect(next.stations?.[0]?.overrides?.black_borders?.params).toEqual({ dark_level: 55 });
    expect(profile.stations?.[0]?.overrides?.black_borders?.params).toEqual({ dark_level: 60 });
  });
  it("tirar o ajuste limpa o nível e volta a herdar", () => {
    const next = withRuleChange(profile, "cg-e3", "black_borders", { param: "dark_level", value: undefined });
    expect(next.stations?.[0]?.overrides).toEqual({});
  });
  it("liga e desliga no perfil inteiro", () => {
    const off = withRuleChange(profile, null, "duplicate_page", { enabled: false });
    expect(off.detectors?.duplicate_page).toEqual({ enabled: false });
    const back = withRuleChange(off, null, "duplicate_page", { enabled: undefined });
    expect(back.detectors?.duplicate_page).toBeUndefined();
  });
});
