// Tela de Sequência: ordem de trabalho, mover páginas, digitação rápida e desfazer.
// Funções puras, para testar sem a tela.
import type { Numbering, QaDocument } from "../api/types";

/** Uma mudança enviada ao motor: números digitados (null desfaz) e, se vier, a ordem. */
export interface SequenceStep {
  values: Record<string, string | null>;
  order?: string[] | null;
}

/** Ordem em que o revisor está trabalhando: a escolhida por ele ou a do arquivo. */
export function workingOrder(doc: Pick<QaDocument, "page_ids" | "manual_order">): string[] {
  return doc.manual_order?.page_ids ?? doc.page_ids;
}

/** Move a página da posição ``index`` em ``delta`` casas (Alt + setas); fora da faixa, nada muda. */
export function moveItem(order: string[], index: number, delta: number): string[] {
  const to = index + delta;
  if (index < 0 || index >= order.length || to < 0 || to >= order.length) return order;
  const next = [...order];
  next.splice(to, 0, ...next.splice(index, 1));
  return next;
}

/** Solta a página ``id`` na posição ``to`` (arrastar). */
export function dropAt(order: string[], id: string, to: number): string[] {
  const from = order.indexOf(id);
  if (from < 0) return order;
  const next = order.filter((p) => p !== id);
  next.splice(Math.max(0, Math.min(to > from ? to - 1 : to, next.length)), 0, id);
  return next;
}

const DOUBT = new Set<Numbering["state"]>(["ambiguous", "illegible", "inferred", "absent"]);

/** A página precisa do revisor: numeração duvidosa e ainda não digitada. */
export function needsTyping(n: Numbering | undefined): boolean {
  return !n || (n.typed === undefined && DOUBT.has(n.state));
}

/**
 * Próxima posição para digitar depois de ``from``: a próxima que precisa do revisor;
 * sem nenhuma adiante, a seguinte; no fim, ``null``.
 */
export function nextToType(order: string[], numbering: Record<string, Numbering | undefined>, from: number): number | null {
  for (let i = from + 1; i < order.length; i++) if (needsTyping(numbering[order[i] ?? ""])) return i;
  return from + 1 < order.length ? from + 1 : null;
}

/** Primeira posição que precisa do revisor (onde a digitação começa). */
export function firstToType(order: string[], numbering: Record<string, Numbering | undefined>): number {
  const i = order.findIndex((pid) => needsTyping(numbering[pid]));
  return i < 0 ? 0 : i;
}

/** O passo que desfaz ``step``, a partir do estado antes dele. */
export function inverse(
  step: SequenceStep,
  before: { typed: Record<string, string | undefined>; manualOrder: string[] | undefined },
): SequenceStep {
  const values: Record<string, string | null> = {};
  for (const pid of Object.keys(step.values)) values[pid] = before.typed[pid] ?? null;
  const undo: SequenceStep = { values };
  if (step.order !== undefined) undo.order = before.manualOrder ?? null;
  return undo;
}

/** O valor digitado mudou alguma coisa? (em branco não grava; igual ao vigente também não) */
export function typedChange(draft: string, n: Numbering | undefined): string | null {
  const value = draft.trim();
  if (!value) return null;
  if (n?.typed === value) return null;
  if (n?.typed === undefined && n?.value === value && n.state === "read") return null;
  return value;
}

/** Prefixo do arquivo de uma folha inserida depois (área de complementos do lote). */
export const COMPLEMENT_PREFIX = ":complemento:/";

export function isInserted(sourceFile: string): boolean {
  return sourceFile.startsWith(COMPLEMENT_PREFIX);
}

export type SequenceKey = { type: "move"; delta: 1 | -1 } | { type: "undo" };

/** Atalhos da tela: Alt + setas move a página; Ctrl+Z desfaz. */
export function sequenceKey(e: { key: string; altKey?: boolean; ctrlKey?: boolean; metaKey?: boolean }): SequenceKey | null {
  const key = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && key === "z") return { type: "undo" };
  if (!e.altKey) return null;
  if (key === "arrowleft" || key === "arrowup") return { type: "move", delta: -1 };
  if (key === "arrowright" || key === "arrowdown") return { type: "move", delta: 1 };
  return null;
}
