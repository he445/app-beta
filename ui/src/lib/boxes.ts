// Caixas do lote e o que ainda segura o relatório de cada uma (mesma regra do motor,
// application/box_report.py): a caixa é a primeira pasta do documento e só sinalização
// médio ou acima sem decisão impede a conclusão; baixa é tratada em massa.
import type { Analysis, Finding, Severity } from "../api/types";
import { ruleLabel } from "./format";

const BLOCKING: ReadonlySet<Severity> = new Set(["medium", "high", "critical"]);

export interface BoxPending {
  box: string;
  pending: Finding[];
}

/** A caixa de um documento: a primeira pasta (ou o próprio lote, sem pastas). */
export function boxOf(documentName: string, batchName: string): string {
  const parts = documentName.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts.length > 1 ? parts[0]! : batchName;
}

/** Sinalizações que ainda impedem cada caixa de ser concluída, na ordem do lote. */
export function boxesPending(report: Analysis): BoxPending[] {
  const owner = new Map<string, string>();
  const order: string[] = [];
  for (const doc of report.documents) {
    const box = boxOf(doc.name, report.batch.name);
    if (!order.includes(box)) order.push(box);
    owner.set(doc.id, box);
    for (const pid of doc.page_ids) owner.set(pid, box);
  }
  const pending = new Map<string, Finding[]>(order.map((b) => [b, []]));
  for (const f of report.findings) {
    const box = owner.get(f.target.id);
    if (box && BLOCKING.has(f.severity) && !f.decision) pending.get(box)!.push(f);
  }
  return order.map((box) => ({ box, pending: pending.get(box)! }));
}

/** "3 sinalizações sem decisão (2 Inclinação, 1 Página faltando)". */
export function pendingText(pending: Finding[]): string {
  const byRule = new Map<string, number>();
  for (const f of pending) byRule.set(f.rule, (byRule.get(f.rule) ?? 0) + 1);
  const parts = [...byRule.entries()].map(([rule, n]) => `${n} ${ruleLabel(rule)}`);
  return `${pending.length} sinalização(ões) sem decisão (${parts.join(", ")})`;
}
