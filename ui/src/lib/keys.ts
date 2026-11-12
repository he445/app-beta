// Atalhos da revisão (docs/operacao/interface.md), como função pura para poder testar.
import type { DecisionAction, Severity } from "../api/types";
import { SEVERITIES } from "./format";

export type ReviewAction =
  | { type: "decide"; action: DecisionAction }
  | { type: "move"; delta: 1 | -1 }
  | { type: "zoom" }
  | { type: "undo" }
  | { type: "filter"; severity: Severity }
  | { type: "numbering" }
  | { type: "rotate"; delta: 90 | 180 | 270 };

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
  if (key === "e") return { type: "rotate", delta: 90 };
  if (key === "q") return { type: "rotate", delta: 270 };
  if (key === "w") return { type: "rotate", delta: 180 };
  const n = Number(key);
  const severity = Number.isInteger(n) ? SEVERITIES[n - 1] : undefined;
  if (severity) return { type: "filter", severity };
  return null;
}

export function isTyping(target: EventTarget | null): boolean {
  if (typeof HTMLElement === "undefined" || !(target instanceof HTMLElement)) return false;
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
  ["Q / E", "Girar a página 90° para a esquerda / direita"],
  ["W", "Girar a página 180°"],
];

/**
 * Giro horário total já aplicado na cópia de uma página: o da sinalização de orientação
 * decidida como "corrigir" (0 se não houver).
 */
export function currentRotation(findings: { rule: string; target: { kind: string; id: string }; decision?: { action: string } | null; correction: { params?: Record<string, unknown> } }[], pageId: string): number {
  const applied = findings.find(
    (f) => f.rule === "orientation" && f.target.kind === "page" && f.target.id === pageId && f.decision?.action === "correct",
  );
  return Number(applied?.correction.params?.angle_deg ?? 0) % 360;
}

/** Novo giro total depois de girar mais ``delta`` graus no sentido horário. */
export function nextRotation(current: number, delta: number): number {
  return (current + delta) % 360;
}

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

export interface ShortcutGroup {
  id: "global" | "review" | "sequence" | "zoom";
  title: string;
  items: [string, string][];
}

/** Todos os atalhos do programa, por tela (tela de atalhos, tecla ?). */
export const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    id: "global",
    title: "Em qualquer tela",
    items: [
      ["?", "Mostrar esta lista de atalhos"],
      ["Esc", "Fechar a lista, o zoom ou a janela aberta"],
    ],
  },
  { id: "review", title: "Revisão", items: SHORTCUTS },
  {
    id: "sequence",
    title: "Sequência",
    items: [
      ["Enter", "No campo do número: grava e vai para a próxima página com dúvida"],
      ["Tab", "Passa para a próxima página com dúvida sem gravar"],
      ["Esc", "No campo do número: volta ao valor anterior"],
      ["Alt + ← →", "Move a página uma posição para a esquerda / direita"],
      ["Ctrl+Z", "Desfaz a última numeração ou mudança de ordem"],
      ["Z ou duplo clique", "Amplia a página"],
    ],
  },
  {
    id: "zoom",
    title: "Página ampliada",
    items: [
      ["← →", "Página anterior / seguinte"],
      ["Espaço", "Mais zoom / menos zoom"],
      ["Esc", "Fecha"],
    ],
  },
];

/** A tecla ? abre a lista de atalhos (fora de campos de texto). */
export function isHelpKey(e: KeyLike & { target?: EventTarget | null }): boolean {
  if (e.ctrlKey || e.metaKey || e.altKey) return false;
  return e.key === "?" && !isTyping(e.target ?? null);
}
