// Tela 6: sequência do documento, numeração lida, lacunas e reordenação proposta.
import { useMemo, useState } from "react";
import { useDecide, usePageImage, useReport } from "../api/hooks";
import type { Analysis, Finding, Page, QaDocument } from "../api/types";
import { Card, ErrorBox, Loading, SeverityBadge, StateDot, Thumb } from "../components/ui";
import { DECISION_LABEL, NUMBERING_STATE_LABEL, ruleLabel } from "../lib/format";
import { href, navigate } from "../router";
import { NumberingDialog } from "./Review";

export function Sequence({ id, doc }: { id: string; doc?: string }) {
  const report = useReport(id);
  if (report.isLoading) return <Loading />;
  if (!report.data) return <div className="page"><ErrorBox error={report.error} /></div>;
  const r = report.data;
  const selected = r.documents.find((d) => d.id === doc) ?? r.documents[0];
  return (
    <div className="split">
      <aside className="doc-list">
        {r.documents.map((d) => (
          <a key={d.id} href={href({ name: "sequence", id, doc: d.id })} className={d.id === selected?.id ? "active" : ""}>
            <StateDot state={d.state} /> {d.name}
          </a>
        ))}
      </aside>
      <main className="page">{selected && <DocumentSequence report={r} document={selected} />}</main>
    </div>
  );
}

function DocumentSequence({ report, document }: { report: Analysis; document: QaDocument }) {
  const pages = useMemo(() => new Map(report.pages.map((p) => [p.id, p])), [report.pages]);
  const docPages = document.page_ids.map((pid) => pages.get(pid)).filter((p): p is Page => Boolean(p));
  const findings = report.findings.filter(
    (f) => f.target.id === document.id || document.page_ids.includes(f.target.id),
  );
  const byPage = new Map<string, Finding[]>();
  for (const f of findings) if (f.target.kind === "page") byPage.set(f.target.id, [...(byPage.get(f.target.id) ?? []), f]);
  const gaps = findings.filter((f) => f.rule === "missing_page" && f.correction.params?.after_page_id);
  const docFindings = findings.filter((f) => f.target.kind === "document");
  const reorder = findings.find((f) => f.rule === "out_of_order");
  const decide = useDecide(report.batch.id);
  const [editing, setEditing] = useState<Page | null>(null);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{document.name}</h1>
          <p className="muted">{docPages.length} página(s). Clique numa página para corrigir a numeração.</p>
        </div>
        <a className="button" href={href({ name: "metadata", id: report.batch.id, doc: document.id })}>Metadados</a>
      </div>

      {docFindings.length > 0 && (
        <Card title="Sinalizações do documento">
          <ul className="plain">
            {docFindings.map((f) => (
              <li key={f.id} className="row tight">
                <SeverityBadge severity={f.severity} /> <strong>{ruleLabel(f.rule)}</strong> {f.message}
                {f.decision && <span className="tag">{DECISION_LABEL[f.decision.action]}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <h2>Como está no arquivo</h2>
      <div className="strip">
        {docPages.map((p) => (
          <SequencePage key={p.id} page={p} findings={byPage.get(p.id) ?? []} gap={gaps.find((g) => g.correction.params?.after_page_id === p.id)} onClick={() => setEditing(p)} />
        ))}
      </div>

      {document.proposed_order.length > 0 && reorder && (
        <>
          <div className="row">
            <h2>Ordem proposta pela numeração</h2>
            {reorder.decision ? (
              <span className="tag">{DECISION_LABEL[reorder.decision.action]}</span>
            ) : (
              <button
                className="primary"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ findingId: reorder.id, action: "correct" })}
              >
                Aceitar a reordenação
              </button>
            )}
          </div>
          <div className="strip">
            {document.proposed_order.map((pid, i) => {
              const p = pages.get(pid);
              const moved = document.page_ids[i] !== pid;
              return p ? (
                <div key={pid} className={`seq-page ${moved ? "moved" : ""}`}>
                  <Thumb pageId={pid} width={120} />
                  <div className="seq-label">{p.numbering?.value ?? "—"}</div>
                  {moved && <div className="small">antes: posição {p.index + 1}</div>}
                </div>
              ) : null;
            })}
          </div>
        </>
      )}

      {editing && (
        <NumberingDialog batchId={report.batch.id} pageId={editing.id} initial={editing.numbering?.value ?? ""} onClose={() => setEditing(null)} />
      )}
      <p><button className="link" onClick={() => navigate({ name: "review", id: report.batch.id })}>← Voltar à revisão</button></p>
    </>
  );
}

function Corner({ pageId }: { pageId: string }) {
  const img = usePageImage(pageId, "original", 480);
  return (
    <div
      className="corner"
      title="Canto da numeração ampliado"
      style={img.data ? { backgroundImage: `url(${img.data})` } : undefined}
    />
  );
}

function SequencePage({ page, findings, gap, onClick }: { page: Page; findings: Finding[]; gap?: Finding; onClick: () => void }) {
  const n = page.numbering;
  const doubt = n && ["inferred", "ambiguous", "illegible"].includes(n.state);
  const missing = (gap?.correction.params?.missing as string[] | undefined) ?? [];
  return (
    <>
      <button className={`seq-page ${doubt ? "doubt" : ""}`} onClick={onClick} title={findings.map((f) => f.message).join("\n")}>
        <Thumb pageId={page.id} width={120} />
        <Corner pageId={page.id} />
        <div className="seq-label">
          {n?.value ?? "—"} {n && <span className={`state-tag st-${n.state}`}>{NUMBERING_STATE_LABEL[n.state]}</span>}
        </div>
        {n && n.previous.length > 0 && <div className="small struck">{n.previous.join(", ")}</div>}
        <div className="seq-flags">
          {findings.map((f) => <SeverityBadge key={f.id} severity={f.severity} />)}
        </div>
      </button>
      {gap && (
        <div className="gap" role="note">
          <strong>Falta</strong>
          <span>fls. {missing.join(", ")}</span>
        </div>
      )}
    </>
  );
}
