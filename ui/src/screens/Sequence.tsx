// Tela 6: sequência do documento. Mostra como está no arquivo ("Antes") e, depois do
// "Corrigir tudo", como fica o lote corrigido ("Depois"), com página faltando decidida à mão.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  useBulkOperations,
  useDecide,
  usePlan,
  useReport,
  useNumberingCrop,
  useSaveCorrected,
  useSetDocumentNumbering,
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
import { isTyping, thumbnailKey } from "../lib/keys";
import {
  dropAt,
  firstToType,
  inverse,
  moveItem,
  needsTyping,
  nextToType,
  sequenceKey,
  typedChange,
  workingOrder,
  type SequenceStep,
} from "../lib/sequence";
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
            key={selected.id}
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
  const order = workingOrder(document);
  const docPages = order.map((pid) => pages.get(pid)).filter((p): p is Page => Boolean(p));
  const numbering = useMemo(() => Object.fromEntries(docPages.map((p) => [p.id, p.numbering])), [docPages]);
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
  const setDoc = useSetDocumentNumbering(batchId, document.id);
  const [history, setHistory] = useState<SequenceStep[]>([]);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const [focusAt, setFocusAt] = useState<number | null>(() =>
    docPages.some((p) => needsTyping(p.numbering)) ? firstToType(order, numbering) : null,
  );

  // O foco vai para a página indicada (na digitação, já; ao mover, depois de gravar).
  useEffect(() => {
    if (focusAt === null) return;
    const input = inputs.current[focusAt];
    if (input) {
      input.focus();
      input.select();
    }
    setFocusAt(null);
  }, [focusAt, report]);

  // As gravações vão em fila: quem digita rápido não perde nada e as respostas chegam em ordem.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  function enqueue(step: SequenceStep, onDone?: () => void) {
    queue.current = queue.current
      .then(() => setDoc.mutateAsync(step))
      .then(onDone, () => undefined);
  }

  function apply(step: SequenceStep, focusAfterSave?: number | null) {
    const typed = Object.fromEntries(docPages.map((p) => [p.id, p.numbering?.typed]));
    const undo = inverse(step, { typed, manualOrder: document.manual_order?.page_ids });
    enqueue(step, () => {
      setHistory((h) => [...h, undo]);
      if (focusAfterSave !== undefined) setFocusAt(focusAfterSave);
    });
  }

  function undoLast() {
    const last = history.at(-1);
    if (!last) return;
    setHistory((h) => h.slice(0, -1));
    enqueue(last);
  }

  function commit(index: number, draft: string) {
    const pid = order[index];
    if (!pid) return;
    const value = typedChange(draft, numbering[pid]);
    const next = nextToType(order, value ? { ...numbering, [pid]: { ...numbering[pid]!, typed: value } } : numbering, index);
    if (value) apply({ values: { [pid]: value } });
    setFocusAt(next);
  }

  function move(index: number, delta: 1 | -1) {
    const next = moveItem(order, index, delta);
    if (next !== order) apply({ values: {}, order: next }, index + delta);
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      if (sequenceKey(e)?.type === "undo") {
        e.preventDefault();
        undoLast();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
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
            {docPages.length} página(s). Digite a numeração embaixo de cada página: Enter grava e vai
            para a próxima com dúvida, Tab passa sem gravar. Arraste a página ou use Alt + setas para
            mudar a ordem; Ctrl+Z desfaz. “Ampliar”, duplo clique ou Z abre a página inteira.
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
          <button onClick={undoLast} disabled={!history.length || setDoc.isPending} title="Desfaz a última numeração ou mudança de ordem (Ctrl+Z)">
            Desfazer
          </button>
          <a className="button" href={href({ name: "metadata", id: batchId, doc: document.id })}>Metadados</a>
        </div>
      </div>
      <ErrorBox error={start.error ?? setDoc.error} />

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

      {document.manual_order ? (
        <div className="row wrap">
          <h2>{changed ? "Antes — ordem escolhida pelo revisor" : "Ordem escolhida pelo revisor"}</h2>
          <span className="small muted">
            {document.manual_order.reviewer} · {new Date(document.manual_order.decided_at).toLocaleString("pt-BR")}
          </span>
          <button className="small-btn" disabled={setDoc.isPending} onClick={() => apply({ values: {}, order: null })}>
            Voltar à ordem do arquivo
          </button>
        </div>
      ) : (
        <h2>{changed ? "Antes — como está no arquivo" : "Como está no arquivo"}</h2>
      )}
      <div className="strip" aria-label="Antes">
        {before.map((s, i) => (
          <StripItem key={s.page.id} s={s} findings={byPage.get(s.page.id) ?? []} mode="before"
            onClick={() => clicks.click({ strip: before, index: i })}
            onDoubleClick={() => clicks.doubleClick({ strip: before, index: i })}
            onKey={(k) => (k === "numbering" ? setEditing(s.page) : openZoom(before, i))}
            position={i + 1}
            inputRef={(el) => {
              inputs.current[i] = el;
            }}
            onCommit={(draft) => commit(i, draft)}
            onMove={(delta) => move(i, delta)}
            onUndo={undoLast}
            onDropPage={(id, after) => {
              const next = dropAt(order, id, after ? i + 1 : i);
              if (next.join() !== order.join()) apply({ values: {}, order: next });
            }}
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

function Corner({ page, variant }: { page: Page; variant: "original" | "corrected" }) {
  const fromImage = page.numbering?.source === "image" && variant === "original";
  const crop = useNumberingCrop(page.id, fromImage);
  const pageId = page.id;
  if (crop.data) {
    return (
      <div className="corner-wrap crop" title="Onde a numeração foi lida">
        <img src={crop.data} alt="" />
      </div>
    );
  }
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
  position,
  inputRef,
  onCommit,
  onMove,
  onUndo,
  onDropPage,
}: {
  s: StripPage;
  findings: Finding[];
  mode: "before" | "after";
  onClick: () => void;
  onDoubleClick: () => void;
  onKey: (k: "numbering" | "zoom") => void;
  after?: React.ReactNode;
  position?: number;
  inputRef?: (el: HTMLInputElement | null) => void;
  onCommit?: (draft: string) => void;
  onMove?: (delta: 1 | -1) => void;
  onUndo?: () => void;
  onDropPage?: (id: string, after: boolean) => void;
}) {
  const [dropSide, setDropSide] = useState<"before" | "after" | null>(null);
  const field = useRef<HTMLInputElement | null>(null);
  const editable = mode === "before" && onCommit;
  const shortcut = (e: React.KeyboardEvent) => {
    const k = sequenceKey(e);
    if (!k || (k.type === "undo" && e.currentTarget.tagName === "INPUT")) return false;
    e.preventDefault();
    if (k.type === "move") onMove?.(k.delta);
    else onUndo?.();
    return true;
  };
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
    dropSide ? `drop-${dropSide}` : "",
  ].join(" ");
  const current = n?.typed ?? n?.value ?? "";
  // O valor vigente muda depois de gravar; quem está digitando no campo não perde o rascunho.
  useEffect(() => {
    if (field.current && window.document.activeElement !== field.current) field.current.value = current;
  }, [current]);
  return (
    <>
      <div
        className={classes}
        draggable={Boolean(editable)}
        onDragStart={(e) => {
          e.dataTransfer.setData("text/x-qa-page", page.id);
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(e) => {
          if (!onDropPage || !e.dataTransfer.types.includes("text/x-qa-page")) return;
          e.preventDefault();
          const box = e.currentTarget.getBoundingClientRect();
          setDropSide(e.clientX > box.left + box.width / 2 ? "after" : "before");
        }}
        onDragLeave={() => setDropSide(null)}
        onDrop={(e) => {
          const id = e.dataTransfer.getData("text/x-qa-page");
          const side = dropSide;
          setDropSide(null);
          if (!id || !onDropPage) return;
          e.preventDefault();
          onDropPage(id, side === "after");
        }}
      >
        <button
          className="seq-hit"
          onClick={onClick}
          onDoubleClick={onDoubleClick}
          onKeyDown={(e) => {
            if (shortcut(e)) return;
            const k = thumbnailKey(e);
            if (!k) return;
            e.preventDefault();
            onKey(k);
          }}
          title={findings.map((f) => f.message).join("\n")}
          aria-label={`Página ${page.index + 1}${removed ? ", removida" : ""}: corrigir numeração`}
        >
          <Thumb pageId={page.id} width={120} variant={variant} />
          <Corner page={page} variant={variant} />
          {mode === "after" ? (
            <div className="seq-label">{item?.target_file?.split("/").pop()}</div>
          ) : (
            <div className="seq-label">
              {n?.value ?? "—"}{" "}
              {n && <span className={`state-tag st-${n.typed !== undefined ? "typed" : n.state}`}>{n.typed !== undefined ? "digitado" : NUMBERING_STATE_LABEL[n.state]}</span>}
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
        {editable && (
          <input
            ref={(el) => {
              field.current = el;
              inputRef?.(el);
            }}
            className={`seq-input ${needsTyping(n) ? "doubt" : ""}`}
            defaultValue={current}
            placeholder="fls."
            aria-label={`Numeração da página na posição ${position}`}
            autoComplete="off"
            onFocus={(e) => e.currentTarget.select()}
            onKeyDown={(e) => {
              if (shortcut(e)) return;
              if (e.key === "Enter") {
                e.preventDefault();
                onCommit(e.currentTarget.value);
              } else if (e.key === "Escape") {
                e.currentTarget.value = current;
                e.currentTarget.blur();
              }
            }}
          />
        )}
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
