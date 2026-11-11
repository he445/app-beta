// Telas 4 e 5: fila de revisão e detalhe da página, operadas pelo teclado.
import { useEffect, useMemo, useRef, useState } from "react";
import { useDecide, usePageImage, useReport, useRotate, useSetNumbering, useUndo } from "../api/hooks";
import type { Analysis, DecisionAction, Severity } from "../api/types";
import { BulkBatchButton } from "../components/BulkButton";
import { Viewer, type ViewerHandle } from "../components/Viewer";
import { ErrorBox, Loading, SeverityBadge, Thumb } from "../components/ui";
import {
  CORRECTION_KIND_LABEL,
  DECISION_LABEL,
  NUMBERING_STATE_LABEL,
  SEVERITIES,
  SEVERITY_LABEL,
  friendlyParams,
  num,
  pct,
  ruleLabel,
} from "../lib/format";
import { SHORTCUTS, currentRotation, isTyping, keyToAction, nextRotation } from "../lib/keys";
import { buildQueue, clampIndex, type QueueFilter, type QueueItem } from "../lib/queue";
import { href } from "../router";

export function Review({ id }: { id: string }) {
  const report = useReport(id);
  if (report.isLoading) return <Loading />;
  if (report.error || !report.data) return <div className="page"><ErrorBox error={report.error} /></div>;
  return <ReviewQueue report={report.data} />;
}

function ReviewQueue({ report }: { report: Analysis }) {
  const batchId = report.batch.id;
  const [filter, setFilter] = useState<QueueFilter>({ severity: null, rule: null, pendingOnly: true });
  const [index, setIndex] = useState(0);
  const [history, setHistory] = useState<string[]>([]);
  const [numberingOpen, setNumberingOpen] = useState(false);
  const [toast, setToast] = useState<{ text: string; n: number } | null>(null);
  const setMessage = (text: string) => setToast((t) => ({ text, n: (t?.n ?? 0) + 1 }));
  const viewer = useRef<ViewerHandle>(null);
  const decide = useDecide(batchId);
  const undo = useUndo(batchId);
  const rotateMutation = useRotate(batchId);
  const correctedPages = useMemo(
    () =>
      new Set(
        report.findings
          .filter((f) => f.target.kind === "page" && f.decision?.action === "correct" && f.correction.kind === "automatic")
          .map((f) => f.target.id),
      ),
    [report.findings],
  );

  function rotate(delta: 90 | 180 | 270) {
    const pageId = current?.page?.id;
    if (!pageId || rotateMutation.isPending) return;
    const angle = nextRotation(currentRotation(report.findings, pageId), delta);
    rotateMutation.mutate(
      { pageId, angle },
      {
        onSuccess: (res) => {
          setHistory((h) => [...h, res.finding.id]);
          setMessage(angle ? `Página girada ${angle}° na cópia.` : "Página de volta à orientação original.");
        },
        onError: (err) => setMessage(err.message),
      },
    );
  }

  const queue = useMemo(() => buildQueue(report, filter), [report, filter]);
  const current = queue[clampIndex(index, queue.length)];
  const rules = useMemo(() => [...new Set(report.findings.map((f) => f.rule))].sort(), [report.findings]);
  const done = report.findings.filter((f) => f.decision).length;

  // Pré-carrega a imagem da próxima sinalização: a decisão seguinte não espera a rede.
  usePageImage(queue[clampIndex(index + 1, queue.length)]?.imagePage?.id);

  function act(action: DecisionAction) {
    if (!current || decide.isPending) return;
    const finding = current.finding;
    decide.mutate(
      { findingId: finding.id, action },
      {
        onSuccess: (res) => {
          setHistory((h) => [...h, finding.id]);
          const rest = res.applied?.remaining_rules ?? [];
          setMessage(
            res.applied
              ? `Correção aplicada numa cópia${rest.length ? `; ainda dispara: ${rest.map(ruleLabel).join(", ")}` : "; reanálise limpa"}.`
              : `${ruleLabel(finding.rule)}: ${DECISION_LABEL[action].toLowerCase()}.`,
          );
          // Só pendentes: a fila encolhe e o mesmo índice já aponta para o próximo.
          if (!filter.pendingOnly) setIndex((i) => clampIndex(i + 1, queue.length));
        },
        onError: (err) => setMessage(err.message),
      },
    );
  }

  function undoLast() {
    const last = history[history.length - 1];
    if (!last || undo.isPending) return;
    undo.mutate(last, {
      onSuccess: () => {
        setHistory((h) => h.slice(0, -1));
        setMessage("Última decisão desfeita.");
        const pos = buildQueue(
          { ...report, findings: report.findings.map((f) => (f.id === last ? { ...f, decision: undefined } : f)) },
          filter,
        ).findIndex((i) => i.finding.id === last);
        if (pos >= 0) setIndex(pos);
      },
      onError: (err) => setMessage(err.message),
    });
  }

  function toggleSeverity(severity: Severity) {
    setFilter((f) => ({ ...f, severity: f.severity === severity ? null : severity }));
    setIndex(0);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isTyping(e.target) || numberingOpen) return;
      const action = keyToAction(e);
      if (!action) return;
      e.preventDefault();
      switch (action.type) {
        case "decide":
          return act(action.action);
        case "move":
          return setIndex((i) => clampIndex(i + action.delta, queue.length));
        case "zoom":
          return viewer.current?.toggleZoom();
        case "undo":
          return undoLast();
        case "filter":
          return toggleSeverity(action.severity);
        case "numbering":
          if (current?.page) setNumberingOpen(true);
          return;
        case "rotate":
          return rotate(action.delta);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="review">
      <aside className="queue">
        <div className="queue-head">
          <div className="queue-progress">
            <strong>{done}</strong> de {report.findings.length} decididas
            <div className="progress small"><div style={{ width: pct(report.findings.length ? done / report.findings.length : 0) }} /></div>
          </div>
          <BulkBatchButton batchId={batchId} className="full" />
          <div className="filters">
            {SEVERITIES.map((sev, i) => (
              <button
                key={sev}
                className={`chip-btn sev-${sev} ${filter.severity === sev ? "active" : ""}`}
                onClick={() => toggleSeverity(sev)}
                title={`Tecla ${i + 1}`}
              >
                {SEVERITY_LABEL[sev]}
              </button>
            ))}
          </div>
          <div className="row">
            <select
              aria-label="Filtrar por defeito"
              value={filter.rule ?? ""}
              onChange={(e) => {
                setFilter((f) => ({ ...f, rule: e.target.value || null }));
                setIndex(0);
              }}
            >
              <option value="">Todos os defeitos</option>
              {rules.map((r) => <option key={r} value={r}>{ruleLabel(r)}</option>)}
            </select>
            <label className="check">
              <input
                type="checkbox"
                checked={filter.pendingOnly}
                onChange={(e) => {
                  setFilter((f) => ({ ...f, pendingOnly: e.target.checked }));
                  setIndex(0);
                }}
              />
              Só pendentes
            </label>
          </div>
        </div>
        <ol className="queue-list">
          {queue.map((item, i) => (
            <QueueRow
              key={item.finding.id}
              item={item}
              active={item === current}
              corrected={Boolean(item.imagePage && correctedPages.has(item.imagePage.id))}
              onClick={() => setIndex(i)}
            />
          ))}
        </ol>
        {queue.length === 0 && <p className="muted pad">Nada na fila com esses filtros.</p>}
      </aside>

      <main className="detail">
        {current ? (
          <Detail
            item={current}
            viewer={viewer}
            busy={decide.isPending || rotateMutation.isPending}
            onDecide={act}
            onNumbering={() => setNumberingOpen(true)}
            onRotate={rotate}
            rotation={current.page ? currentRotation(report.findings, current.page.id) : 0}
            pageCorrected={Boolean(current.imagePage && correctedPages.has(current.imagePage.id))}
          />
        ) : (
          <div className="empty">
            <h2>Fila vazia</h2>
            <p className="muted">Tudo decidido. Veja o <a href={href({ name: "reports", id: batchId })}>relatório e a ordem de retrabalho</a>.</p>
          </div>
        )}
        {toast && (
          <div key={toast.n} className="toast" role="status" onAnimationEnd={() => setToast(null)}>
            {toast.text}
          </div>
        )}
      </main>

      {numberingOpen && current?.page && (
        <NumberingDialog batchId={batchId} pageId={current.page.id} initial={current.page.numbering?.value ?? ""} onClose={() => setNumberingOpen(false)} />
      )}
    </div>
  );
}

function QueueRow({ item, active, corrected, onClick }: { item: QueueItem; active: boolean; corrected: boolean; onClick: () => void }) {
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: "nearest" });
  }, [active]);
  const f = item.finding;
  return (
    <li ref={ref} className={`queue-row ${active ? "active" : ""} ${f.decision ? "decided" : ""}`} onClick={onClick}>
      <Thumb pageId={item.imagePage?.id} width={56} variant={corrected ? "corrected" : "original"} />
      <div className="queue-text">
        <div className="row tight">
          <SeverityBadge severity={f.severity} />
          <span className="rule">{ruleLabel(f.rule)}</span>
        </div>
        <div className="muted small ellipsis">
          {item.document?.name}
          {item.page ? ` · p. ${item.page.index + 1}` : " · documento"}
        </div>
        {f.decision && <div className="small decided-label">{DECISION_LABEL[f.decision.action]}</div>}
      </div>
    </li>
  );
}

function Detail({
  item,
  viewer,
  busy,
  onDecide,
  onNumbering,
  onRotate,
  rotation,
  pageCorrected,
}: {
  item: QueueItem;
  viewer: React.RefObject<ViewerHandle>;
  busy: boolean;
  onDecide: (a: DecisionAction) => void;
  onNumbering: () => void;
  onRotate: (delta: 90 | 180 | 270) => void;
  rotation: number;
  pageCorrected: boolean;
}) {
  const f = item.finding;
  const corrected = pageCorrected && f.target.kind === "page";
  const [showAfter, setShowAfter] = useState(true);
  const variant = corrected && showAfter ? "corrected" : "original";
  const image = usePageImage(item.imagePage?.id, variant);
  const fallback = usePageImage(item.imagePage?.id, "original");
  const url = image.isError ? fallback.data : image.data;
  const params = friendlyParams(f.correction.params);
  const page = item.page;

  return (
    <div className="detail-grid">
      <div className="viewer-wrap">
        <Viewer ref={viewer} url={url} region={variant === "original" ? f.region : undefined} label={ruleLabel(f.rule)} />
        {corrected && (
          <div className="before-after">
            <button className={!showAfter ? "active" : ""} onClick={() => setShowAfter(false)}>Antes</button>
            <button className={showAfter ? "active" : ""} onClick={() => setShowAfter(true)}>Depois</button>
          </div>
        )}
        {!url && <Loading label="Carregando a imagem…" />}
      </div>

      <div className="panel">
        <div className="row tight">
          <SeverityBadge severity={f.severity} />
          <h2 className="inline">{ruleLabel(f.rule)}</h2>
        </div>
        <p className="message">{f.message}</p>

        <dl className="facts">
          <dt>Medida</dt><dd>{num(f.measure, 3)}</dd>
          <dt>Limiar</dt><dd>{num(f.threshold, 3)}</dd>
          <dt>Confiança</dt><dd>{pct(f.confidence)}</dd>
          <dt>Regra</dt><dd><code>{f.rule}</code> v{f.rule_version}</dd>
        </dl>

        <div className={`proposal kind-${f.correction.kind}`}>
          <div className="small muted">{CORRECTION_KIND_LABEL[f.correction.kind]}</div>
          <div>{f.correction.description}</div>
          {params && <div className="small muted">{params}</div>}
        </div>

        <div className="actions">
          <button disabled={busy} onClick={() => onDecide("approve")}><kbd>A</kbd> Aprovar</button>
          <button disabled={busy} className="primary" onClick={() => onDecide("correct")}><kbd>C</kbd> Corrigir</button>
          <button disabled={busy} className="danger" onClick={() => onDecide("reject")}><kbd>R</kbd> Retrabalho</button>
          <button disabled={busy} onClick={() => onDecide("source_defect")}><kbd>O</kbd> Defeito de origem</button>
        </div>
        {f.decision && (
          <p className="small muted">
            {DECISION_LABEL[f.decision.action]} por {f.decision.reviewer} em {new Date(f.decision.decided_at).toLocaleString("pt-BR")}
          </p>
        )}

        {page && (
          <div className="rotation">
            <h3>Girar a página</h3>
            <div className="row tight">
              <button disabled={busy} onClick={() => onRotate(270)} title="Tecla Q"><kbd>Q</kbd> ↺ 90°</button>
              <button disabled={busy} onClick={() => onRotate(90)} title="Tecla E"><kbd>E</kbd> ↻ 90°</button>
              <button disabled={busy} onClick={() => onRotate(180)} title="Tecla W"><kbd>W</kbd> 180°</button>
            </div>
            <p className="small muted">
              {rotation ? `Na cópia: girada ${rotation}° no sentido horário.` : "Na cópia: orientação original."} O
              original não muda.
            </p>
          </div>
        )}

        <h3>Página</h3>
        <dl className="facts">
          <dt>Documento</dt><dd>{item.document?.name}</dd>
          {page && (
            <>
              <dt>Arquivo</dt><dd className="ellipsis" title={page.source_file}>{page.source_file}</dd>
              <dt>Posição</dt><dd>{page.index + 1} de {item.document?.page_ids.length}</dd>
              <dt>Resolução</dt><dd>{page.dpi ? `${num(page.dpi, 0)} dpi` : "não gravada"}</dd>
              <dt>Estação</dt><dd>{page.station ?? "—"}</dd>
              <dt>Numeração</dt>
              <dd>
                {page.numbering ? `${page.numbering.value ?? "—"} (${NUMBERING_STATE_LABEL[page.numbering.state]})` : "—"}
                <button className="link" onClick={onNumbering}><kbd>N</kbd> corrigir</button>
              </dd>
            </>
          )}
        </dl>
        {item.document && (
          <a className="small" href={href({ name: "sequence", id: item.document.batch_id, doc: item.document.id })}>
            Ver a sequência do documento →
          </a>
        )}

        <details className="shortcuts">
          <summary>Atalhos</summary>
          <dl>{SHORTCUTS.map(([k, v]) => <div key={k}><dt><kbd>{k}</kbd></dt><dd>{v}</dd></div>)}</dl>
        </details>
      </div>
    </div>
  );
}

export function NumberingDialog({ batchId, pageId, initial, onClose }: { batchId: string; pageId: string; initial: string; onClose: () => void }) {
  const [value, setValue] = useState(initial);
  const setNumbering = useSetNumbering(batchId);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => input.current?.select(), []);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form
        className="modal card"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.key === "Escape" && onClose()}
        onSubmit={(e) => {
          e.preventDefault();
          setNumbering.mutate({ pageId, value: value.trim() }, { onSuccess: onClose });
        }}
      >
        <h2>Numeração da folha</h2>
        <p className="muted small">Ex.: 12, 12-A, 12v. A sequência do documento é recalculada.</p>
        <input ref={input} value={value} onChange={(e) => setValue(e.target.value)} aria-label="Numeração" autoFocus />
        <ErrorBox error={setNumbering.error} />
        <div className="row">
          <button type="button" onClick={onClose}>Cancelar</button>
          <button className="primary" disabled={!value.trim() || setNumbering.isPending}>Salvar</button>
        </div>
      </form>
    </div>
  );
}
