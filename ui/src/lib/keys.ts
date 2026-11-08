// Atalhos da revisão (seção 12 do ADD), como função pura para poder testar.
import type { DecisionAction, Severity } from "../api/types";
import { SEVERITIES } from "./format";

export type ReviewAction =
  | { type: "decide"; action: DecisionAction }
  | { type: "move"; delta: 1 | -1 }
  | { type: "zoom" }
  | { type: "undo" }
  | { type: "filter"; severity: Severity }
  | { type: "numbering" };

export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
}

const DECISIONS: Record<string, DecisionAction> = {
  a: "approve",
  c: "correct",
  r: "reject",
  o: "source_defect",
};

export function keyToAction(e: KeyLike): ReviewAction | null {
  const key = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && key === "z") return { type: "undo" };
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  const decision = DECISIONS[key];
  if (decision) return { type: "decide", action: decision };
  if (key === "arrowright" || key === "arrowdown") return { type: "move", delta: 1 };
  if (key === "arrowleft" || key === "arrowup") return { type: "move", delta: -1 };
  if (key === " " || key === "spacebar") return { type: "zoom" };
  if (key === "n") return { type: "numbering" };
  const n = Number(key);
  const severity = Number.isInteger(n) ? SEVERITIES[n - 1] : undefined;
  if (severity) return { type: "filter", severity };
  return null;
}

export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export const SHORTCUTS: [string, string][] = [
  ["A", "Aprovar (falso positivo)"],
  ["C", "Aplicar a correção proposta"],
  ["R", "Reprovar e mandar para retrabalho"],
  ["O", "Defeito de origem"],
  ["← →", "Anterior / seguinte"],
  ["Espaço", "Ampliar / reduzir"],
  ["Ctrl+Z", "Desfazer a última decisão"],
  ["1–4", "Filtrar por severidade"],
  ["N", "Digitar a numeração da página"],
];

export type ZoomKeyAction = "close" | "prev" | "next" | "zoom";

/** Teclado do modal de zoom: Esc fecha, setas passam de página, espaço amplia. */
export function zoomModalKey(e: KeyLike): ZoomKeyAction | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  const key = e.key.toLowerCase();
  if (key === "escape" || key === "esc") return "close";
  if (key === "arrowleft") return "prev";
  if (key === "arrowright") return "next";
  if (key === " " || key === "spacebar") return "zoom";
  return null;
}

/** Teclado de uma miniatura da sequência: Enter abre a numeração, Z abre o zoom. */
export function thumbnailKey(e: KeyLike): "numbering" | "zoom" | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  const key = e.key.toLowerCase();
  if (key === "enter") return "numbering";
  if (key === "z") return "zoom";
  return null;
}
