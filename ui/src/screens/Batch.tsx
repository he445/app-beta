// Telas 2 e 3: processamento ao vivo e painel do lote.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { keys, useBatch, useReport } from "../api/hooks";
import { streamEvents } from "../api/sse";
import type { Analysis, BatchStatus } from "../api/types";
import { BulkBatchButton } from "../components/BulkButton";
import { Bar, Card, ErrorBox, Loading, SeverityBadge, Stat } from "../components/ui";
import { SEVERITIES, VERDICT_LABEL, pct, ruleLabel } from "../lib/format";
import { href } from "../router";

export function Batch({ id }: { id: string }) {
  const batch = useBatch(id);
  const qc = useQueryClient();
  const status = batch.data;
  const analyzed = status?.status === "analyzed";
  const report = useReport(id, analyzed);

  const running = status ? status.status === "queued" || status.status === "processing" : false;
  useEffect(() => {
    if (!running) return;
    const ctrl = new AbortController();
    streamEvents(
      `/batches/${id}/events`,
      (e) => qc.setQueryData<BatchStatus>(keys.batch(id), JSON.parse(e.data) as BatchStatus),
      ctrl.signal,
    ).catch(() => undefined); // o polling de useBatch continua como reserva
    return () => ctrl.abort();
  }, [id, running, qc]);

  if (batch.isLoading) return <Loading />;
  if (batch.error) return <div className="page"><ErrorBox error={batch.error} /></div>;
  if (!status) return null;
  if (status.status === "failed")
    return (
      <div className="page">
        <h1>{status.name}</h1>
        <div className="error">A análise falhou: {status.error}</div>
      </div>
    );
  if (!analyzed) return <Processing status={status} />;
  if (report.isLoading || !report.data) return <Loading label="Carregando o relatório…" />;
  return <Dashboard report={report.data} />;
}

function Processing({ status }: { status: BatchStatus }) {
  const started = useRef<{ t: number; done: number } | null>(null);
  const [rate, setRate] = useState<number | null>(null);
  const { done, total } = status.progress;
  useEffect(() => {
    if (done === 0) return;
    if (!started.current) started.current = { t: performance.now(), done };
    const elapsed = (performance.now() - started.current.t) / 1000;
    if (elapsed > 0.5) setRate((done - started.current.done) / elapsed);
  }, [done]);
  const ratio = total ? done / total : 0;
  return (
    <div className="page narrow">
      <h1>{status.name}</h1>
      <Card>
        <p>{status.status === "queued" ? "Na fila…" : `Analisando ${done} de ${total} páginas`}</p>
        <div className="progress" role="progressbar" aria-valuenow={done} aria-valuemax={total}>
          <div style={{ width: `${ratio * 100}%` }} />
        </div>
        <p className="muted">{rate ? `${rate.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} páginas por segundo` : " "}</p>
      </Card>
    </div>
  );
}

function Dashboard({ report }: { report: Analysis }) {
  const s = report.batch.summary;
  const id = report.batch.id;
  const pending = report.findings.filter((f) => !f.decision).length;
  const states = Object.values(s.document_states);
  const count = (st: string) => states.filter((x) => x === st).length;
  const rules = Object.entries(s.by_rule).sort((a, b) => b[1] - a[1]);
  const stations = Object.entries(s.by_station).sort((a, b) => b[1] - a[1]);
  const maxRule = Math.max(1, ...rules.map(([, n]) => n));
  const maxStation = Math.max(1, ...stations.map(([, n]) => n));
  const tone = s.verdict === "approved" ? "ok" : s.verdict === "rejected" ? "bad" : "warn";

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{report.batch.name}</h1>
          <p className="muted">
            Perfil {report.batch.profile_id} · analisado em {new Date(report.batch.analyzed_at).toLocaleString("pt-BR")}
          </p>
        </div>
        <div className="row wrap">
          <BulkBatchButton batchId={id} />
          <a className="button primary" href={href({ name: "review", id })}>
            Revisar {pending} pendente(s)
          </a>
        </div>
      </div>

      <div className="stats">
        <Stat label="Veredito" value={VERDICT_LABEL[s.verdict]} tone={tone} />
        <Stat label="Dispensam revisão" value={pct(s.no_review_ratio)} hint={`${s.pages_without_review} de ${s.pages_total} páginas`} tone={s.no_review_ratio >= 0.5 ? "ok" : "warn"} />
        <Stat label="Documentos" value={s.documents_total} hint={`${count("green")} verdes · ${count("yellow")} amarelos · ${count("red")} vermelhos`} />
        <Stat label="Amostra dos verdes" value={s.green_sample.length} hint="documentos sorteados para conferência" />
      </div>

      <div className="grid-3">
        <Card title="Por severidade">
          {SEVERITIES.map((sev) => (
            <div className="bar-row" key={sev}>
              <SeverityBadge severity={sev} />
              <Bar value={s.by_severity[sev] ?? 0} max={Math.max(1, ...Object.values(s.by_severity))} tone={sev} />
              <span className="num">{s.by_severity[sev] ?? 0}</span>
            </div>
          ))}
        </Card>
        <Card title="Por defeito">
          {rules.map(([rule, n]) => (
            <div className="bar-row" key={rule}>
              <span className="bar-label">{ruleLabel(rule)}</span>
              <Bar value={n} max={maxRule} />
              <span className="num">{n}</span>
            </div>
          ))}
        </Card>
        <Card title="Por estação (médio ou acima)">
          {stations.length === 0 && <p className="muted">Nenhum defeito relevante.</p>}
          {stations.map(([station, n]) => (
            <div className="bar-row" key={station}>
              <span className="bar-label">{station}</span>
              <Bar value={n} max={maxStation} />
              <span className="num">{n}</span>
            </div>
          ))}
        </Card>
      </div>

      {s.lossy_files.length > 0 && (
        <div className="warning">
          {s.lossy_files.length} arquivo(s) com compressão com perda; o Anexo I do Decreto 10.278/2020 exige compressão sem perda.
        </div>
      )}

      <Card title="Documentos">
        <div className="doc-chips">
          {report.documents.map((d) => (
            <a key={d.id} className={`chip state-${d.state}`} href={href({ name: "sequence", id, doc: d.id })}>
              {d.name}
              {s.green_sample.includes(d.id) && <span className="tag">amostra</span>}
            </a>
          ))}
        </div>
      </Card>
    </div>
  );
}
