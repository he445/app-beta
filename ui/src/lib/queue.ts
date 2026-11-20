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
  /** Só as sinalizações desta pasta (documento); ``null`` ou ausente = todas as pastas. */
  document?: string | null;
}

/** A pasta (documento) de uma sinalização: a do alvo, ou o próprio documento. */
export function findingDocument(report: Analysis, f: Finding, pages?: Map<string, Page>): string | undefined {
  if (f.target.kind === "document") return f.target.id;
  const page = (pages ?? new Map(report.pages.map((p) => [p.id, p]))).get(f.target.id);
  return page?.document_id;
}

export interface FolderCount {
  document: QaDocument;
  pending: number;
  total: number;
}

/** Sinalizações de cada pasta (sem decisão e no total), na ordem do lote. */
export function folderCounts(report: Analysis): FolderCount[] {
  const pages = new Map(report.pages.map((p) => [p.id, p]));
  const counts = new Map(report.documents.map((d) => [d.id, { pending: 0, total: 0 }]));
  for (const f of report.findings) {
    const c = counts.get(findingDocument(report, f, pages) ?? "");
    if (!c) continue;
    c.total += 1;
    if (!f.decision) c.pending += 1;
  }
  return report.documents.map((document) => ({ document, ...counts.get(document.id)! }));
}

/** A próxima pasta com pendência depois de ``current`` (dá a volta); a primeira sem ``current``. */
export function nextPendingFolder(counts: FolderCount[], current?: string | null): string | undefined {
  const start = current ? counts.findIndex((c) => c.document.id === current) : -1;
  for (let step = 1; step <= counts.length; step++) {
    const c = counts[(start + step + counts.length) % counts.length]!;
    if (c.pending > 0 && c.document.id !== current) return c.document.id;
  }
  return undefined;
}

export function isPending(f: Finding): boolean {
  return !f.decision || f.decision.action === "reject";
}

export function buildQueue(report: Analysis, filter: QueueFilter): QueueItem[] {
  const pages = new Map(report.pages.map((p) => [p.id, p]));
  const docs = new Map(report.documents.map((d) => [d.id, d]));
  const docOrder = new Map(report.documents.map((d, i) => [d.id, i]));
  const items: QueueItem[] = report.findings
    .filter((f) => !filter.document || findingDocument(report, f, pages) === filter.document)
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
