import type { DecisionAction, Severity } from "../api/types";

export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Crítico",
  high: "Alto",
  medium: "Médio",
  low: "Baixo",
};

export const RULE_LABEL: Record<string, string> = {
  corrupted_file: "Arquivo corrompido",
  low_resolution: "Resolução abaixo do exigido",
  blank_page: "Página em branco",
  black_borders: "Bordas pretas",
  blur: "Desfoque",
  skew: "Inclinação",
  exposure: "Escura, clara ou sem contraste",
  duplicate_page: "Página duplicada",
  missing_page: "Página faltando",
  out_of_order: "Fora de ordem",
  numbering_review: "Revisar numeração",
  completeness_unverifiable: "Completude não verificável",
};

export const DECISION_LABEL: Record<DecisionAction, string> = {
  approve: "Aprovada (falso positivo)",
  correct: "Corrigida",
  reject: "Retrabalho",
  source_defect: "Defeito de origem",
};

export const VERDICT_LABEL: Record<string, string> = {
  approved: "Aprovado",
  approved_with_reservations: "Aprovado com ressalvas",
  rejected: "Reprovado",
};

export const CORRECTION_KIND_LABEL: Record<string, string> = {
  automatic: "Automática, na cópia",
  physical: "Ação física",
  escalate: "Decisão humana",
};

export const NUMBERING_STATE_LABEL: Record<string, string> = {
  read: "lido",
  inferred: "inferido",
  renumbered: "renumerado",
  ambiguous: "ambíguo",
  illegible: "ilegível",
  absent: "ausente",
};

export const SOURCE_LABEL: Record<string, string> = {
  file_tag: "Tag do arquivo",
  file_mtime: "Data do arquivo",
  profile: "Perfil",
  generated: "Gerado",
  computed: "Calculado",
  ocr: "OCR",
  reviewer: "Revisor",
  unavailable: "Indisponível",
};

export function ruleLabel(rule: string): string {
  return RULE_LABEL[rule] ?? rule;
}

export function pct(value: number, digits = 0): string {
  return `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: digits })}%`;
}

export function num(value: number, digits = 2): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: digits });
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Parâmetros da correção úteis ao revisor (sem identificadores internos). */
export function friendlyParams(params: Record<string, unknown> | undefined): string {
  return Object.entries(params ?? {})
    .filter(([k]) => !k.endsWith("_id") && k !== "order" && k !== "duplicate_of")
    .map(([k, v]) => `${k}: ${formatValue(v)}`)
    .join(" · ");
}
