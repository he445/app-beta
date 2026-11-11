// O mesmo build serve nuvem, desktop e servidor: as telas decidem pelo que o motor oferece
// (capabilities), nunca pelo modo. Só a partida e a ponte da janela conhecem o desktop.
import { describe, expect, it } from "vitest";

const ALLOWED = new Set(["./desktop.ts", "./session.ts", "../api/engine.tsx", "../api/schema.d.ts", "../api/types.ts"]);

const sources = import.meta.glob(["../**/*.ts", "../**/*.tsx", "!../**/*.test.ts"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("sem verificação de modo fora do contexto", () => {
  it("lê o código das telas", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(20);
  });

  it("nenhuma tela compara o modo do motor nem procura a janela do desktop", () => {
    const offenders = Object.entries(sources)
      .filter(([path]) => !ALLOWED.has(path))
      .filter(([, text]) => /\.mode\b|"desktop"|pywebview/.test(text))
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});
