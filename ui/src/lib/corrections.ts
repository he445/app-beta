// Estado das telas de correção em lote (TAREFAS 3 e 4), como funções puras.
import type { BulkCorrection, CorrectedDocument, CorrectedPage, CorrectedPlan } from "../api/types";
import { ruleLabel } from "./format";

export function isActive(op: BulkCorrection | undefined): boolean {
  return op?.status === "queued" || op?.status === "running";
}

/** Operação em andamento no lote (no máximo uma). */
export function activeOperation(ops: BulkCorrection[] | undefined): BulkCorrection | undefined {
  return ops?.find(isActive);
}

/** Operações aplicadas, com algo aplicado e ainda não salvas, que cobrem o documento. */
export function unsavedOperations(
  ops: BulkCorrection[] | undefined,
  documentId: string | undefined,
): BulkCorrection[] {
  return (ops ?? []).filter(
    (op) =>
      op.status === "applied" &&
      (op.result?.applied_total ?? 0) > 0 &&
      (op.scope.kind === "batch" || op.scope.id === documentId),
  );
}

/** A mais recente de ``unsavedOperations``. */
export function unsavedOperation(
  ops: BulkCorrection[] | undefined,
  documentId: string | undefined,
): BulkCorrection | undefined {
  return unsavedOperations(ops, documentId)[0];
}

/** Soma das correções aplicadas por regra em várias operações. */
export function mergeApplied(ops: BulkCorrection[]): Record<string, number> {
  const total: Record<string, number> = {};
  for (const op of ops)
    for (const [rule, n] of Object.entries(op.result?.applied_by_rule ?? {})) total[rule] = (total[rule] ?? 0) + n;
  return total;
}

export interface ProgressView {
  title: string;
  detail: string;
  percent: number;
  tone: "info" | "ok" | "bad";
  finished: boolean;
}

/** Tela de carregamento: progresso real (unidades corrigidas de um total). */
export function progressView(op: BulkCorrection | undefined): ProgressView {
  if (!op) return { title: "Preparando…", detail: "", percent: 0, tone: "info", finished: false };
  const { done, total, current } = op.progress;
  const percent = total ? Math.round((done / total) * 100) : op.status === "queued" ? 0 : 100;
  switch (op.status) {
    case "queued":
      return { title: "Na fila…", detail: "A correção começa em instantes.", percent: 0, tone: "info", finished: false };
    case "running":
      return {
        title: `Corrigindo ${done} de ${total}`,
        detail: current ? `Agora: ${current}` : "",
        percent,
        tone: "info",
        finished: false,
      };
    case "failed":
      return { title: "A correção falhou", detail: op.error ?? "", percent, tone: "bad", finished: true };
    case "undone":
      return { title: "Correções desfeitas", detail: "", percent: 100, tone: "info", finished: true };
    default:
      return {
        title: total ? `${op.result?.applied_total ?? done} correção(ões) aplicada(s)` : "Nada automático para corrigir",
        detail: "",
        percent: 100,
        tone: "ok",
        finished: true,
      };
  }
}

export interface SaveState {
  enabled: boolean;
  reason: string | null;
}

/** "Salvar correções" só libera sem página faltando pendente e sem correção em andamento. */
export function saveState(plan: CorrectedPlan | undefined, ops: BulkCorrection[] | undefined): SaveState {
  if (!plan) return { enabled: false, reason: "Carregando o plano do lote corrigido…" };
  if (activeOperation(ops)) return { enabled: false, reason: "Espere a correção terminar." };
  if (plan.blockers.length) {
    const which = plan.blockers.map((b) => b.document).join(", ");
    return {
      enabled: false,
      reason: `Decida a página faltando antes de salvar (${which}): retrabalho, defeito de origem ou aprovar mesmo assim.`,
    };
  }
  return { enabled: true, reason: null };
}

/** Faixa "Depois": páginas exportadas na ordem final. */
export function afterStrip(doc: CorrectedDocument): CorrectedPage[] {
  return doc.pages
    .filter((p) => p.status === "exported")
    .sort((a, b) => (a.new_position ?? 0) - (b.new_position ?? 0));
}

/** O documento muda no lote corrigido? */
export function hasChanges(doc: CorrectedDocument): boolean {
  return doc.reordered || doc.pages.some((p) => p.corrected || p.moved || p.status === "removed");
}

export interface DocumentMarks {
  changes: number;
  missingPending: number;
  rescan: number;
}

export function documentMarks(doc: CorrectedDocument): DocumentMarks {
  return {
    changes: doc.pages.filter((p) => p.corrected || p.moved || p.status === "removed").length,
    missingPending: doc.missing.filter((m) => !m.decision).length,
    rescan: doc.pages.filter((p) => p.needs_rescan.length > 0).length,
  };
}

/** "Inclinação 1, Página em branco 1". */
export function appliedText(byRule: Record<string, number>): string {
  return Object.entries(byRule)
    .map(([rule, n]) => `${ruleLabel(rule)} ${n}`)
    .join(" · ");
}

export const SKIP_LABEL: Record<string, string> = {
  missing_page: "página faltando (decida abaixo)",
  needs_rescan: "precisa redigitalizar",
  manual: "exige decisão humana",
  failed: "não foi possível corrigir",
};

/** Contagem do que ficou pendente, só do documento informado (ou do lote). */
export function skippedText(op: BulkCorrection | undefined, targetIds?: Set<string>): string {
  const counts = new Map<string, number>();
  for (const s of op?.result?.skipped ?? []) {
    if (targetIds && !targetIds.has(s.target.id)) continue;
    counts.set(s.category, (counts.get(s.category) ?? 0) + 1);
  }
  return [...counts.entries()].map(([c, n]) => `${n} ${SKIP_LABEL[c] ?? c}`).join(" · ");
}
