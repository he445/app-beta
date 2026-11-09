// Tela 6: sequência do documento. Mostra como está no arquivo ("Antes") e, depois do
// "Corrigir tudo", como fica o lote corrigido ("Depois"), com página faltando decidida à mão.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  useBulkOperations,
  useDecide,
  usePlan,
  useReport,
  useSaveCorrected,
  useStartBulk,
  useUndo,
  useUndoBulk,
} from "../api/hooks";
import type {
  Analysis,
  BulkCorrection,
  CorrectedDocument,
  CorrectedPage,
  CorrectedPlan,
  DecisionAction,
  Finding,
  MissingGap,
  Page,
  QaDocument,
} from "../api/types";
import { CorrectionProgress } from "../components/CorrectionProgress";
import { Card, ErrorBox, Loading, SeverityBadge, StateDot, Thumb } from "../components/ui";
import { ZoomModal, type ZoomPage } from "../components/ZoomModal";
import { createClickController } from "../lib/clicks";
import {
  activeOperation,
  afterStrip,
  appliedText,
  documentMarks,
  hasChanges,
  mergeApplied,
  saveState,
  skippedText,
  unsavedOperations,
} from "../lib/corrections";
import { DECISION_LABEL, NUMBERING_STATE_LABEL, ruleLabel } from "../lib/format";
import { thumbnailKey } from "../lib/keys";
import { href, navigate } from "../router";
import { NumberingDialog } from "./Review";

export function Sequence({ id, doc }: { id: string; doc?: string }) {
  const report = useReport(id);
  const plan = usePlan(id, Boolean(report.data));
  const ops = useBulkOperations(id);
  const active = activeOperation(ops.data);
  const finishing = useFinishingOperation(ops.data, active);
  const r = report.data;
  const selected = r?.documents.find((d) => d.id === doc) ?? r?.documents[0];
  const docPlans = useMemo(
    () => new Map((plan.data?.documents ?? []).map((d) => [d.document_id, d])),
    [plan.data],
  );

  // Depois de "Corrigir o lote inteiro", abre o primeiro documento que mudou.
  const lastFinished = useRef<string | null>(null);
  useEffect(() => {
    const latest = ops.data?.[0];
    if (!latest || latest.status !== "applied" || latest.scope.kind !== "batch" || !plan.data) return;
    if (lastFinished.current === latest.id) return;
    lastFinished.current = latest.id;
    const current = selected ? docPlans.get(selected.id) : undefined;
    if (current && hasChanges(current)) return;
    const changed = plan.data.documents.find(hasChanges);
    if (changed) navigate({ name: "sequence", id, doc: changed.document_id });
  }, [ops.data, plan.data, docPlans, selected, id]);

  if (report.isLoading) return <Loading />;
  if (!r) return <div className="page"><ErrorBox error={report.error} /></div>;
  return (
    <div className="split">
      <aside className="doc-list">
        {r.documents.map((d) => {
          const marks = docPlans.get(d.id) ? documentMarks(docPlans.get(d.id)!) : null;
          return (
            <a key={d.id} href={href({ name: "sequence", id, doc: d.id })} className={d.id === selected?.id ? "active" : ""}>
              <StateDot state={d.state} /> <span className="ellipsis">{d.name}</span>
              {marks && marks.missingPending > 0 && <span className="mark mark-missing" title="Página faltando sem decisão">falta folha</span>}
              {marks && marks.rescan > 0 && <span className="mark mark-rescan" title="Páginas a redigitalizar">{marks.rescan} redigitalizar</span>}
              {marks && marks.changes > 0 && <span className="mark mark-ok" title="Páginas que mudam no lote corrigido">✓ {marks.changes}</span>}
            </a>
          );
        })}
      </aside>
      <main className="page sequence-main">
        {selected && (
          <DocumentSequence
            report={r}
            document={selected}
            docPlan={docPlans.get(selected.id)}
            plan={plan.data}
            ops={ops.data}
          />
        )}
        {(active ?? finishing) && <CorrectionProgress op={active ?? finishing} />}
      </main>
    </div>
  );
}

/** Mantém o estado final da operação na tela de carregamento por um instante. */
function useFinishingOperation(ops: BulkCorrection[] | undefined, active: BulkCorrection | undefined) {
  const [finishing, setFinishing] = useState<BulkCorrection | undefined>();
  const last = useRef<string | null>(null);
  useEffect(() => {
    if (active) {
      last.current = active.id;
      return;
    }
    if (!last.current) return;
    const done = ops?.find((op) => op.id === last.current);
    if (!done) return;
    last.current = null;
    setFinishing(done);
  }, [ops, active]);
  useEffect(() => {
    if (!finishing) return;
    const timer = setTimeout(() => setFinishing(undefined), 1500);
    return () => clearTimeout(timer);
  }, [finishing]);
  return finishing;
}

interface StripPage {
  page: Page;
  item: CorrectedPage | undefined;
  corrected: boolean;
}

function DocumentSequence({
  report,
  document,
  docPlan,
  plan,
  ops,
}: {
  report: Analysis;
  document: QaDocument;
  docPlan: CorrectedDocument | undefined;
  plan: CorrectedPlan | undefined;
  ops: BulkCorrection[] | undefined;
}) {
  const batchId = report.batch.id;
  const pages = useMemo(() => new Map(report.pages.map((p) => [p.id, p])), [report.pages]);
  const items = useMemo(() => new Map((docPlan?.pages ?? []).map((p) => [p.page_id, p])), [docPlan]);
  const docPages = document.page_ids.map((pid) => pages.get(pid)).filter((p): p is Page => Boolean(p));
  const findings = report.findings.filter((f) => f.target.id === document.id || document.page_ids.includes(f.target.id));
  const byPage = new Map<string, Finding[]>();
  for (const f of findings) if (f.target.kind === "page") byPage.set(f.target.id, [...(byPage.get(f.target.id) ?? []), f]);
  const docFindings = findings.filter((f) => f.target.kind === "document" && f.rule !== "missing_page");
  const reorder = findings.find((f) => f.rule === "out_of_order");

  const start = useStartBulk(batchId);
  const undoBulk = useUndoBulk(batchId);
  const save = useSaveCorrected(batchId, report.batch.name);
  const decide = useDecide(batchId);
  const [editing, setEditing] = useState<Page | null>(null);
  const [zoom, setZoom] = useState<{ pages: ZoomPage[]; index: number; preferCorrected: boolean } | null>(null);

  const active = activeOperation(ops);
  const unsavedOps = unsavedOperations(ops, document.id);
  const unsaved = unsavedOps[0];
  const lastOp = ops?.find((op) => op.status !== "undone" && (op.scope.kind === "batch" || op.scope.id === document.id));
  const canSave = saveState(plan, ops);
  const targets = useMemo(() => new Set([document.id, ...document.page_ids]), [document]);
  const changed = docPlan ? hasChanges(docPlan) : false;

  const before: StripPage[] = docPages.map((page) => ({ page, item: items.get(page.id), corrected: false }));
  const after: StripPage[] = docPlan
    ? afterStrip(docPlan).map((item) => ({ page: pages.get(item.page_id)!, item, corrected: item.corrected }))
    : [];

  const clicks = useMemo(
    () =>
      createClickController<{ strip: StripPage[]; index: number }>(
        ({ strip, index }) => {
          const target = strip[index];
          if (target) setEditing(target.page);
        },
        ({ strip, index }) => openZoom(strip, index),
      ),
    [],
  );
  useEffect(() => () => clicks.cancel(), [clicks]);

  function openZoom(strip: StripPage[], index: number) {
    const corrected = strip.some((s) => s.corrected);
    setZoom({
      pages: strip.map((s) => ({
        pageId: s.page.id,
        label: s.item?.target_file && corrected ? s.item.target_file : `Página ${s.page.index + 1} · ${s.page.source_file}`,
        hasCorrected: Boolean(s.item?.corrected),
      })),
      index,
      preferCorrected: corrected,
    });
  }

  const gapsAfter = (pageId: string) => (docPlan?.missing ?? []).filter((m) => m.after_page_id === pageId);
  const trailingGaps = (docPlan?.missing ?? []).filter((m) => !m.after_page_id);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{document.name}</h1>
          <p className="muted">
            {docPages.length} página(s). Toque ou clique numa página para corrigir a numeração (Enter);
            “Ampliar”, duplo clique ou Z abre a página inteira.
          </p>
        </div>
        <div className="row wrap">
          <button
            className="primary"
            disabled={Boolean(active) || start.isPending}
            onClick={() => start.mutate(document.id)}
            title="Aplica as correções automáticas pendentes deste documento"
          >
            Corrigir tudo
          </button>
          <a className="button" href={href({ name: "metadata", id: batchId, doc: document.id })}>Metadados</a>
        </div>
      </div>
      <ErrorBox error={start.error} />

      {unsaved && (
        <div className="unsaved" role="alert">
          <div>
            <strong>Correções aplicadas e ainda não salvas.</strong>{" "}
            Aplicado {unsavedOps.some((op) => op.scope.kind === "batch") ? "no lote" : "neste documento"}:{" "}
            {appliedText(mergeApplied(unsavedOps))}.{" "}
            O lote corrigido só é gerado quando você salvar.
            {!canSave.enabled && canSave.reason && <div className="small blocked-reason">{canSave.reason}</div>}
          </div>
          <div className="row wrap">
            <button className="primary" disabled={!canSave.enabled || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Gerando o lote…" : "Salvar correções"}
            </button>
            <button
              disabled={undoBulk.isPending}
              onClick={async () => {
                // Desfaz só o que os "Corrigir tudo" ainda não salvos aplicaram, do mais recente ao mais antigo.
                for (const op of unsavedOps) await undoBulk.mutateAsync(op.id);
              }}
            >
              Desfazer correções
            </button>
          </div>
        </div>
      )}
      <ErrorBox error={save.error ?? undoBulk.error} />
      {save.data && !unsaved && (
        <div className="ok-banner" role="status">
          Correções salvas. O lote corrigido ({save.data.totals.exported} páginas, {save.data.totals.removed} removida(s)) foi baixado como{" "}
          <code>{report.batch.name}-{save.data.file}</code>.
        </div>
      )}

      {lastOp?.result && lastOp.status !== "failed" && (
        <p className="small muted">
          {lastOp.scope.kind === "batch" ? "Corrigir o lote inteiro" : "Corrigir tudo"}:{" "}
          {lastOp.result.applied_total ? appliedText(lastOp.result.applied_by_rule) : "nada automático para corrigir"}.
          {skippedText(lastOp, targets) && <> Não corrigido automaticamente: {skippedText(lastOp, targets)}.</>}
        </p>
      )}

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

      <h2>{changed ? "Antes — como está no arquivo" : "Como está no arquivo"}</h2>
      <div className="strip" aria-label="Antes">
        {before.map((s, i) => (
          <StripItem key={s.page.id} s={s} findings={byPage.get(s.page.id) ?? []} mode="before"
            onClick={() => clicks.click({ strip: before, index: i })}
            onDoubleClick={() => clicks.doubleClick({ strip: before, index: i })}
            onKey={(k) => (k === "numbering" ? setEditing(s.page) : openZoom(before, i))}
            after={gapsAfter(s.page.id).map((g) => <MissingCard key={g.finding_id} gap={g} batchId={batchId} />)}
          />
        ))}
        {trailingGaps.map((g) => <MissingCard key={g.finding_id} gap={g} batchId={batchId} />)}
      </div>

      {changed && docPlan && (
        <>
          <h2>Depois — lote corrigido {unsaved && <span className="tag warn">não salvo</span>}</h2>
          <div className="strip" aria-label="Depois">
            {after.map((s, i) => (
              <StripItem key={s.page.id} s={s} findings={[]} mode="after"
                onClick={() => clicks.click({ strip: after, index: i })}
                onDoubleClick={() => clicks.doubleClick({ strip: after, index: i })}
                onKey={(k) => (k === "numbering" ? setEditing(s.page) : openZoom(after, i))}
              />
            ))}
          </div>
        </>
      )}

      {document.proposed_order.length > 0 && reorder && !reorder.decision && (
        <>
          <div className="row">
            <h2>Ordem proposta pela numeração</h2>
            <button className="primary" disabled={decide.isPending} onClick={() => decide.mutate({ findingId: reorder.id, action: "correct" })}>
              Aceitar a reordenação
            </button>
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

      {editing && <NumberingDialog batchId={batchId} pageId={editing.id} initial={editing.numbering?.value ?? ""} onClose={() => setEditing(null)} />}
      {zoom && <ZoomModal {...zoom} onClose={() => setZoom(null)} />}
      <p><button className="link" onClick={() => navigate({ name: "review", id: batchId })}>← Voltar à revisão</button></p>
    </>
  );
}

function Corner({ pageId, variant }: { pageId: string; variant: "original" | "corrected" }) {
  return (
    <div className="corner-wrap" title="Canto da numeração ampliado">
      <Thumb pageId={pageId} width={360} variant={variant} className="corner-img" />
    </div>
  );
}

function StripItem({
  s,
  findings,
  mode,
  onClick,
  onDoubleClick,
  onKey,
  after,
}: {
  s: StripPage;
  findings: Finding[];
  mode: "before" | "after";
  onClick: () => void;
  onDoubleClick: () => void;
  onKey: (k: "numbering" | "zoom") => void;
  after?: React.ReactNode;
}) {
  const { page, item } = s;
  const n = page.numbering;
  const removed = item?.status === "removed";
  const unreadable = item?.status === "not_exported";
  const rescan = item?.needs_rescan ?? [];
  const variant = mode === "after" && s.corrected ? "corrected" : "original";
  const doubt = n && ["inferred", "ambiguous", "illegible"].includes(n.state);
  const marks = mode === "after" ? (item?.changes ?? []).filter((c) => !c.text.startsWith("removida")) : [];
  const classes = [
    "seq-page",
    doubt && mode === "before" ? "doubt" : "",
    removed ? "removed" : "",
    rescan.length || unreadable ? "rescan" : "",
    mode === "after" && (item?.corrected || item?.moved) ? "changed" : "",
  ].join(" ");
  return (
    <>
      <div className={classes}>
        <button
          className="seq-hit"
          onClick={onClick}
          onDoubleClick={onDoubleClick}
          onKeyDown={(e) => {
            const k = thumbnailKey(e);
            if (!k) return;
            e.preventDefault();
            onKey(k);
          }}
          title={findings.map((f) => f.message).join("\n")}
          aria-label={`Página ${page.index + 1}${removed ? ", removida" : ""}: corrigir numeração`}
        >
          <Thumb pageId={page.id} width={120} variant={variant} />
          <Corner pageId={page.id} variant={variant} />
          {mode === "after" ? (
            <div className="seq-label">{item?.target_file?.split("/").pop()}</div>
          ) : (
            <div className="seq-label">
              {n?.value ?? "—"} {n && <span className={`state-tag st-${n.state}`}>{NUMBERING_STATE_LABEL[n.state]}</span>}
            </div>
          )}
          {mode === "before" && n && n.previous.length > 0 && <div className="small struck">{n.previous.join(", ")}</div>}
          {removed && <div className="small note-removed">removida: {item?.reason}</div>}
          {unreadable && <div className="small note-rescan">{item?.reason}</div>}
          {rescan.length > 0 && (
            <div className="small note-rescan" title={rescan.map((r) => r.text).join("\n")}>
              precisa redigitalizar: {rescan.map((r) => ruleLabel(r.rule).toLowerCase()).join(", ")}
            </div>
          )}
          {marks.map((c) => (
            <div key={`${c.finding_id}-${c.text}`} className="small note-change">✓ {c.text}</div>
          ))}
          {mode === "after" && item && !item.moved && item.new_position !== item.old_position && (
            <div className="small muted">antes: posição {item.old_position}</div>
          )}
          {mode === "before" && (
            <div className="seq-flags">
              {findings.map((f) => <SeverityBadge key={f.id} severity={f.severity} />)}
            </div>
          )}
        </button>
        <button className="zoom-btn" onClick={() => onKey("zoom")} aria-label={`Ampliar a página ${page.index + 1}`}>
          Ampliar
        </button>
      </div>
      {after}
    </>
  );
}

const MISSING_OPTIONS: { action: DecisionAction; label: string; hint: string; tone?: string }[] = [
  { action: "reject", label: "Mandar para retrabalho", hint: "localizar a folha e redigitalizar", tone: "danger" },
  { action: "source_defect", label: "Defeito de origem", hint: "o papel já veio sem a folha" },
  { action: "approve", label: "Aprovar mesmo assim", hint: "a numeração estava errada" },
];

const MISSING_DECIDED: Record<DecisionAction, string> = {
  reject: "Mandada para retrabalho (localizar a folha e redigitalizar)",
  source_defect: "Defeito de origem: o papel já veio sem a folha",
  approve: "Aprovada mesmo assim",
  correct: "Corrigida",
};

/** Cartão no lugar da lacuna: página faltando exige decisão manual (TAREFA 4). */
function MissingCard({ gap, batchId }: { gap: MissingGap; batchId: string }) {
  const decide = useDecide(batchId);
  const undo = useUndo(batchId);
  const folios = gap.missing.join(", ");
  const between =
    gap.after_position !== null ? `entre a página ${gap.after_position} e a ${gap.after_position + 1} do arquivo` : "posição desconhecida (contagem declarada)";
  return (
    <div className={`missing-card ${gap.decision ? "decided" : ""}`} role="group" aria-label={`Falta fls. ${folios}`}>
      <strong>{folios ? `Falta fls. ${folios}` : "Página faltando"}</strong>
      <span className="small">{between}</span>
      {gap.decision ? (
        <>
          <span className="small decided-label">{MISSING_DECIDED[gap.decision.action]}</span>
          <span className="small muted">
            {gap.decision.reviewer} · {new Date(gap.decision.decided_at).toLocaleString("pt-BR")}
          </span>
          <button className="small-btn" disabled={undo.isPending} onClick={() => undo.mutate(gap.finding_id)}>Alterar decisão</button>
        </>
      ) : (
        <>
          <span className="small">Exige aprovação manual:</span>
          {MISSING_OPTIONS.map((o) => (
            <button key={o.action} className={`small-btn ${o.tone ?? ""}`} disabled={decide.isPending}
              onClick={() => decide.mutate({ findingId: gap.finding_id, action: o.action })}>
              <span>{o.label}</span>
              <span className="muted">({o.hint})</span>
            </button>
          ))}
        </>
      )}
      <ErrorBox error={decide.error ?? undo.error} />
    </div>
  );
}
