// Fila de revisão: sinalizações ordenadas por severidade, com filtros (tela 4).
import type { Analysis, Finding, Page, QaDocument, Severity } from "../api/types";

const RANK: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export interface QueueItem {
  finding: Finding;
  page: Page | undefined;
  document: QaDocument | undefined;
  /** Página usada para mostrar a imagem (a própria ou a primeira do documento). */
  imagePage: Page | undefined;
}

export interface QueueFilter {
  severity: Severity | null;
  rule: string | null;
  pendingOnly: boolean;
}

export function isPending(f: Finding): boolean {
  return !f.decision || f.decision.action === "reject";
}

export function buildQueue(report: Analysis, filter: QueueFilter): QueueItem[] {
  const pages = new Map(report.pages.map((p) => [p.id, p]));
  const docs = new Map(report.documents.map((d) => [d.id, d]));
  const docOrder = new Map(report.documents.map((d, i) => [d.id, i]));
  const items: QueueItem[] = report.findings
    .filter((f) => !filter.severity || f.severity === filter.severity)
    .filter((f) => !filter.rule || f.rule === filter.rule)
    .filter((f) => !filter.pendingOnly || !f.decision)
    .map((finding) => {
      const page = finding.target.kind === "page" ? pages.get(finding.target.id) : undefined;
      const document = page ? docs.get(page.document_id) : docs.get(finding.target.id);
      const first = document?.page_ids[0];
      return { finding, page, document, imagePage: page ?? (first ? pages.get(first) : undefined) };
    });
  return items.sort(
    (a, b) =>
      RANK[a.finding.severity] - RANK[b.finding.severity] ||
      (docOrder.get(a.document?.id ?? "") ?? 0) - (docOrder.get(b.document?.id ?? "") ?? 0) ||
      (a.page?.index ?? -1) - (b.page?.index ?? -1) ||
      a.finding.rule.localeCompare(b.finding.rule),
  );
}

export function clampIndex(index: number, length: number): number {
  if (length === 0) return 0;
  return Math.min(Math.max(index, 0), length - 1);
}

/** Substitui uma sinalização no relatório em cache após uma decisão. */
export function replaceFinding(report: Analysis, finding: Finding): Analysis {
  return { ...report, findings: report.findings.map((f) => (f.id === finding.id ? finding : f)) };
}
