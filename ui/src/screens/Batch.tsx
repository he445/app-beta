// Telas 2 e 3: processamento ao vivo e painel do lote.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useCapability } from "../api/engine";
import {
  keys,
  useBatch,
  useBoxLocks,
  useBulkOperations,
  useDecideMany,
  usePlan,
  useReport,
  useSaveCorrected,
} from "../api/hooks";
import { streamEvents } from "../api/sse";
import type { Analysis, BatchStatus } from "../api/types";
import { BulkButtons } from "../components/BulkButton";
import { Bar, Card, ErrorBox, Loading, SeverityBadge, Stat } from "../components/ui";
import { lockNotices } from "../lib/boxLocks";
import { activeOperation, foliosText, massDecisionPlan, saveState } from "../lib/corrections";
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
      (e) => {
        if (e.event === "document_ready") void qc.invalidateQueries({ queryKey: keys.report(id) });
        else qc.setQueryData<BatchStatus>(keys.batch(id), JSON.parse(e.data) as BatchStatus);
      },
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
      <BoxLockBanner batchId={status.id} />
      <Card>
        <p>{status.status === "queued" ? "Na fila…" : `Analisando ${done} de ${total} páginas`}</p>
        <div className="progress" role="progressbar" aria-valuenow={done} aria-valuemax={total}>
          <div style={{ width: `${ratio * 100}%` }} />
        </div>
        <p className="muted">{rate ? `${rate.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} páginas por segundo` : " "}</p>
      </Card>
      {status.documents && <ReleaseQueue batchId={status.id} queue={status.documents} />}
    </div>
  );
}

/** Avisos da trava por caixa: caixa assumida por outra máquina ou trava só neste computador. */
function BoxLockBanner({ batchId }: { batchId: string }) {
  // Lote que não veio de pasta responde enabled: false, e a faixa não aparece.
  const locks = useBoxLocks(batchId, useCapability("box_locks"));
  const notices = lockNotices(locks.data);
  if (notices.length === 0) return null;
  return (
    <>
      {notices.map((n) => (
        <div key={n.text} className={n.tone === "bad" ? "error" : "warning"} role="status">
          {n.text}
        </div>
      ))}
    </>
  );
}

/** Fila de processos: o conferente abre o primeiro pronto enquanto o resto é analisado. */
function ReleaseQueue({ batchId, queue }: { batchId: string; queue: NonNullable<BatchStatus["documents"]> }) {
  return (
    <Card title="Processos">
      <p className="small muted">
        Cada processo fica pronto para conferir assim que é analisado. “Corrigir pasta”, “Corrigir tudo” e “Decidir
        semelhantes” já valem para os prontos; juntar o lote corrigido e o relatório da caixa esperam a caixa inteira.
      </p>
      <ul className="plain release-queue">
        {queue.ready.map((d) => (
          <li key={d.id} className="row tight">
            <span className="tag ok">pronto</span> <span className="ellipsis">{d.name}</span>
            <a className="button small-btn" href={href({ name: "sequence", id: batchId, doc: d.id })}>Conferir</a>
          </li>
        ))}
        {queue.pending.map((d, i) => (
          <li key={d.id} className="row tight muted">
            <span className="tag">{i === 0 ? "analisando" : "na fila"}</span> <span className="ellipsis">{d.name}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/**
 * "Salvar caixa": grava a versão corrigida da caixa (o lote corrigido) direto do painel.
 * Na pasta de saída quando o motor grava em pasta; senão baixa o .zip. Salvar também
 * gera o relatório de cada caixa concluída.
 */
function SaveBox({ batchId, batchName }: { batchId: string; batchName: string }) {
  const folder = useCapability("folder_export");
  const plan = usePlan(batchId);
  const ops = useBulkOperations(batchId);
  const save = useSaveCorrected(batchId, batchName, folder ? "folder" : "zip");
  const state = saveState(plan.data, ops.data);
  const saved = save.data;
  return (
    <div className="save-box">
      <div className="row wrap">
        <button
          className="primary"
          disabled={!state.enabled || save.isPending}
          onClick={() => save.mutate()}
          title="Grava a versão corrigida da caixa e gera o relatório das caixas concluídas"
        >
          {save.isPending ? "Salvando a caixa…" : "Salvar caixa"}
        </button>
        {!state.enabled && state.reason && <span className="small blocked-reason">{state.reason}</span>}
        {state.enabled && plan.data && plan.data.pending_critical > 0 && (
          <span className="small warning-text">
            {plan.data.pending_critical} crítica(s) pendente(s): vão como estão e entram na lista de retrabalho.
          </span>
        )}
      </div>
      <ErrorBox error={save.error} />
      {saved && (
        <div className="ok-banner small" role="status">
          Caixa salva: {saved.totals.exported} páginas, {saved.totals.removed} removida(s), {saved.totals.corrected}{" "}
          corrigida(s).{" "}
          {saved.folder ? <>Gravada em <code>{saved.folder}</code>.</> : <>Baixada como <code>{batchName}-{saved.file}</code>.</>}{" "}
          <a href={href({ name: "reports", id: batchId })}>Ver relatório da caixa</a>
        </div>
      )}
    </div>
  );
}

/**
 * "Aprovar tudo como defeito de origem": aceita a caixa como está, com ressalva. Cada
 * sinalização sem decisão vira defeito de origem com a mesma ressalva e sai no relatório
 * ("Defeitos de origem, para o cliente"); nada vai para retrabalho e o veredito fica
 * "aprovado com ressalvas". Página faltando tem alerta próprio, com a lista de pastas e
 * folhas: só entra se o revisor confirmar, e aí o relatório da caixa lista cada uma.
 */
function SourceDefectAll({ report }: { report: Analysis }) {
  const batchId = report.batch.id;
  const plan = massDecisionPlan(report);
  const ops = useBulkOperations(batchId);
  const many = useDecideMany(batchId);
  const [step, setStep] = useState<"closed" | "confirm" | "missing">("closed");
  const [note, setNote] = useState("");
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [result, setResult] = useState<{ total: number; missing: number } | null>(null);
  const busy = many.isPending || Boolean(activeOperation(ops.data));
  const all = plan.ids.length + plan.missing.length;
  const folders = new Set(plan.missing.map((m) => m.folder)).size;

  function run(includeMissing: boolean) {
    const ids = includeMissing ? [...plan.ids, ...plan.missing.map((m) => m.id)] : plan.ids;
    const missing = includeMissing ? plan.missing.length : 0;
    setProgress({ done: 0, total: ids.length });
    many.mutate(
      { findingIds: ids, action: "source_defect", note, onProgress: (done) => setProgress({ done, total: ids.length }) },
      {
        onSuccess: (total) => {
          setResult({ total, missing });
          setStep("closed");
        },
      },
    );
  }

  if (all === 0 && !result) return null;
  return (
    <div className="source-defect-all">
      {step === "closed" && all > 0 && (
        <button onClick={() => setStep("confirm")} disabled={busy} title="Marca todas as sinalizações sem decisão como defeito de origem, com ressalva">
          Aprovar tudo (defeito de origem) · {all}
        </button>
      )}
      {step === "confirm" && (
        <Card title="Aprovar tudo como defeito de origem">
          {plan.ids.length > 0 && (
            <p className="small">
              {plan.ids.length} sinalização(ões) sem decisão vão ser aceitas como estão, como problema que veio do papel:{" "}
              {plan.byRule.map(([rule, n]) => `${n} ${ruleLabel(rule)}`).join(", ")}. Nada vai para retrabalho, o
              veredito fica “aprovado com ressalvas” e a lista sai no relatório para o cliente.
            </p>
          )}
          {plan.missing.length > 0 && (
            <p className="small warning-text">
              Há também {plan.missing.length} página(s) faltando em {folders} pasta(s): no próximo passo você confere a
              lista e decide se entram.
            </p>
          )}
          <form
            className="row wrap"
            onSubmit={(e) => {
              e.preventDefault();
              if (plan.missing.length > 0) setStep("missing");
              else run(false);
            }}
          >
            <input
              className="grow"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ressalva (opcional): ex. papel original com manchas e páginas em branco"
              aria-label="Ressalva"
              disabled={many.isPending}
              autoFocus
            />
            <button className="primary" disabled={busy}>
              {many.isPending && progress
                ? `Gravando ${progress.done} de ${progress.total}…`
                : plan.missing.length > 0
                  ? "Continuar"
                  : "Confirmar"}
            </button>
            <button type="button" onClick={() => setStep("closed")} disabled={many.isPending}>Cancelar</button>
          </form>
          <Progress progress={many.isPending ? progress : null} />
          <ErrorBox error={many.error} />
        </Card>
      )}
      {step === "missing" && (
        <div className="missing-alert" role="alertdialog" aria-labelledby="missing-alert-title">
          <h3 id="missing-alert-title">
            Atenção: {plan.missing.length} página(s) faltando em {folders} pasta(s)
          </h3>
          <p className="small">
            Confirmando, cada uma entra como defeito de origem (o papel já veio sem a folha), com a ressalva
            {note.trim() ? ` “${note.trim()}”` : " em branco"}, e o relatório da caixa lista a pasta e as folhas que
            faltam. Não vai para retrabalho: ninguém vai procurar a folha.
          </p>
          <ul className="plain missing-list">
            {plan.missing.map((m) => (
              <li key={m.id}>
                <strong>{m.folder}</strong>: {m.folios.length ? foliosText(m.folios) : m.message}
              </li>
            ))}
          </ul>
          <div className="row wrap">
            <button className="danger" disabled={busy} onClick={() => run(true)}>
              {many.isPending && progress ? `Gravando ${progress.done} de ${progress.total}…` : "Confirmar, com as páginas faltando"}
            </button>
            {plan.ids.length > 0 && (
              <button disabled={busy} onClick={() => run(false)} title="Decida as páginas faltando uma a uma no cartão da Sequência">
                Só as outras {plan.ids.length}
              </button>
            )}
            <button className="link" disabled={many.isPending} onClick={() => setStep("confirm")}>Voltar</button>
          </div>
          <Progress progress={many.isPending ? progress : null} />
          <ErrorBox error={many.error} />
        </div>
      )}
      {result && step === "closed" && (
        <div className="ok-banner small" role="status">
          {result.total} sinalização(ões) marcadas como defeito de origem
          {result.missing > 0 ? `, ${result.missing} delas página(s) faltando` : ""}
          {note.trim() ? `, com a ressalva “${note.trim()}”` : ""}.{" "}
          {result.missing > 0 && "O relatório da caixa lista a pasta e as folhas. "}
          <a href={href({ name: "reports", id: batchId })}>Ver no relatório</a>
        </div>
      )}
    </div>
  );
}

function Progress({ progress }: { progress: { done: number; total: number } | null }) {
  if (!progress) return null;
  return (
    <div className="progress small" role="progressbar" aria-valuenow={progress.done} aria-valuemax={progress.total}>
      <div style={{ width: `${(progress.done / Math.max(1, progress.total)) * 100}%` }} />
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
          <BulkButtons batchId={id} openSequence />
          <a className="button primary" href={href({ name: "review", id })}>
            Revisar {pending} pendente(s)
          </a>
        </div>
      </div>

      <SaveBox batchId={id} batchName={report.batch.name} />
      <SourceDefectAll report={report} />

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

      <BoxLockBanner batchId={id} />

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
