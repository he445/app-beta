// Regras puras da tela de Configurações: validar antes de mandar e montar o perfil alterado.
import type { ParamView, Profile } from "../api/types";

export const LAYER_LABEL: Record<string, string> = {
  default: "padrão",
  machine: "máquina (TI)",
  user: "você",
  env: "variável QA_*",
  args: "argumento",
  manifest: "padrão da regra",
  profile: "perfil",
  station: "estação",
};

export type Parsed = { value: unknown; error: null } | { value: null; error: string };

const ok = (value: unknown): Parsed => ({ value, error: null });
const bad = (error: string): Parsed => ({ value: null, error });

function number(raw: string): number | null {
  const text = raw.trim().replace(",", ".");
  if (!text || !/^-?\d+(\.\d+)?$/.test(text)) return null;
  return Number(text);
}

/** Valida um parâmetro de regra pelo tipo e pela faixa do manifesto. */
export function parseParam(param: Pick<ParamView, "type" | "minimum" | "maximum">, raw: string | boolean): Parsed {
  if (param.type === "boolean") return typeof raw === "boolean" ? ok(raw) : bad("marque ou desmarque");
  const n = number(String(raw));
  if (n === null) return bad("digite um número");
  if (param.type === "integer" && !Number.isInteger(n)) return bad("digite um número inteiro");
  if (param.minimum !== undefined && n < param.minimum) return bad(`mínimo ${param.minimum}`);
  if (param.maximum !== undefined && n > param.maximum) return bad(`máximo ${param.maximum}`);
  return ok(n);
}

/** Valida um campo da configuração deste computador (as mesmas regras do esquema). */
export function parseComputerField(key: string, raw: string): Parsed {
  const text = raw.trim();
  switch (key) {
    case "workers":
    case "max_memory_mb": {
      if (text === "" || text.toLowerCase() === "auto") return ok("auto");
      const n = number(text);
      const min = key === "workers" ? 1 : 256;
      if (n === null || !Number.isInteger(n)) return bad("“auto” ou um número inteiro");
      if (n < min) return bad(`mínimo ${min}`);
      if (key === "workers" && n > 256) return bad("máximo 256");
      return ok(n);
    }
    case "batch_settle_seconds": {
      const n = number(text);
      if (n === null) return bad("digite um número de segundos");
      return n < 0 || n > 3600 ? bad("entre 0 e 3600") : ok(n);
    }
    case "retention_days": {
      const n = number(text);
      if (n === null) return bad("digite um número de dias");
      return n <= 0 ? bad("maior que zero") : ok(n);
    }
    case "allowed_roots":
      return ok(
        raw
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean),
      );
    case "default_station":
      return text === "" ? ok(null) : /^[a-z0-9_-]+$/.test(text) ? ok(text) : bad("identificador de estação");
    case "log_level":
      return ["debug", "info", "warning", "error"].includes(text) ? ok(text) : bad("debug, info, warning ou error");
    case "output_dir":
    case "temp_dir":
      return ok(text === "" ? null : text);
    case "data_dir":
      return text === "" ? bad("informe a pasta") : ok(text);
    default:
      return ok(text);
  }
}

/** Texto do campo para um valor da configuração. */
export function formatComputerField(key: string, value: unknown): string {
  if (value === null || value === undefined) return "";
  if (key === "allowed_roots" && Array.isArray(value)) return value.join("\n");
  return String(value);
}

type Overrides = Record<string, { enabled?: boolean; params?: Record<string, unknown> }>;

/**
 * Perfil com um ajuste de regra no nível escolhido: o perfil inteiro (``detectors``) ou
 * uma estação (``stations[].overrides``). ``undefined`` tira o ajuste daquele nível, e o
 * valor volta a ser herdado. Não altera o perfil recebido.
 */
export function withRuleChange(
  profile: Profile,
  stationId: string | null,
  rule: string,
  change: { param: string; value: unknown } | { enabled: boolean | undefined },
): Profile {
  const next = structuredClone(profile) as Profile & { detectors?: Overrides };
  let level: Overrides;
  if (stationId) {
    const station = next.stations?.find((s) => s.id === stationId);
    if (!station) throw new Error(`estação ${stationId} não existe no perfil`);
    station.overrides ??= {};
    level = station.overrides as Overrides;
  } else {
    next.detectors ??= {};
    level = next.detectors as Overrides;
  }
  const entry = (level[rule] ??= {});
  if ("param" in change) {
    const params = (entry.params ??= {});
    if (change.value === undefined) delete params[change.param];
    else params[change.param] = change.value;
    if (Object.keys(params).length === 0) delete entry.params;
  } else if (change.enabled === undefined) {
    delete entry.enabled;
  } else {
    entry.enabled = change.enabled;
  }
  if (Object.keys(entry).length === 0) delete level[rule];
  return next;
}
