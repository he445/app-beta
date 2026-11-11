// O mesmo build serve nuvem, desktop e servidor: as telas decidem pelo que o motor oferece
// (capabilities), nunca pelo modo. Só a partida e a ponte da janela conhecem o desktop.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");
const ALLOWED = new Set(["lib/desktop.ts", "lib/session.ts", "api/engine.tsx", "api/schema.d.ts", "api/types.ts"]);

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.tsx?$/.test(name) && !name.endsWith(".test.ts") ? [path] : [];
  });
}

describe("sem verificação de modo fora do contexto", () => {
  it("nenhuma tela compara o modo do motor nem procura a janela do desktop", () => {
    const offenders = files(SRC)
      .map((path) => relative(SRC, path).replaceAll("\\", "/"))
      .filter((rel) => !ALLOWED.has(rel))
      .filter((rel) => /\.mode\b|"desktop"|pywebview/.test(readFileSync(join(SRC, rel), "utf-8")));
    expect(offenders).toEqual([]);
  });
});
