// Tela 8: relatório do lote e ordem de retrabalho por estação.
import { useMutation, useQuery } from "@tanstack/react-query";
import { raw, download } from "../api/client";
import { useCapability } from "../api/engine";
import { usePlan, useReport, useSaveCorrected } from "../api/hooks";
import { Card, ErrorBox, Loading, Stat } from "../components/ui";
import { csvObjects } from "../lib/csv";
import { VERDICT_LABEL, friendlyParams, pct, ruleLabel } from "../lib/format";

function settings(text: string | undefined): string {
  try {
    return friendlyParams(JSON.parse(text ?? "{}") as Record<string, unknown>);
  } catch {
    return text ?? "";
  }
}

const FILES = [
  ["report.json", "Relatório completo (JSON)"],
  ["findings.csv", "Sinalizações (CSV)"],
  ["metadata.csv", "Metadados (CSV)"],
  ["rework_order.csv", "Ordem de retrabalho (CSV)"],
] as const;

export function Reports({ id }: { id: string }) {
  const report = useReport(id);
  const plan = usePlan(id, Boolean(report.data));
  const saveCorrected = useSaveCorrected(id, report.data?.batch.name ?? "lote");
  const saveToFolder = useSaveCorrected(id, report.data?.batch.name ?? "lote", "folder");
  const folderExport = useCapability("folder_export");
  const canDownload = useCapability("upload");
  const exports = useMutation({ mutationFn: () => raw(`/batches/${id}/exports`, { method: "POST" }) });
  const rework = useQuery({
    queryKey: ["rework", id, report.dataUpdatedAt],
    queryFn: async () => {
      await raw(`/batches/${id}/exports`, { method: "POST" });
      const res = await raw(`/batches/${id}/exports/rework_order.csv`);
      return csvObjects(await res.text());
    },
    enabled: Boolean(report.data),
  });

  if (report.isLoading) return <Loading />;
  if (!report.data) return <div className="page"><ErrorBox error={report.error} /></div>;
  const r = report.data;
  const s = r.batch.summary;
  const decided = r.findings.filter((f) => f.decision);
  const sourceDefects = decided.filter((f) => f.decision?.action === "source_defect");
  const falsePositives = decided.filter((f) => f.decision?.action === "approve");
  const byStation = new Map<string, Record<string, string>[]>();
  for (const item of rework.data ?? []) byStation.set(item.station ?? "", [...(byStation.get(item.station ?? "") ?? []), item]);

  async function get(name: string) {
    await exports.mutateAsync();
    await download(`/batches/${id}/exports/${name}`, `${r.batch.name}-${name}`);
  }

  return (
    <div className="page">
      <h1>Relatório — {r.batch.name}</h1>
      <div className="stats">
        <Stat label="Veredito" value={VERDICT_LABEL[s.verdict]} tone={s.verdict === "approved" ? "ok" : s.verdict === "rejected" ? "bad" : "warn"} />
        <Stat label="Decididas" value={`${decided.length} / ${r.findings.length}`} />
        <Stat label="Falsos positivos" value={falsePositives.length} hint="medem a precisão real de cada regra" />
        <Stat label="Defeitos de origem" value={sourceDefects.length} />
        <Stat label="Dispensam revisão" value={pct(s.no_review_ratio)} />
      </div>

      <Card title="Lote corrigido">
        <p className="small muted">
          Mesma estrutura de pastas, páginas na ordem final, removidas fora, versão corrigida de cada
          página, TIFF sem perda com o DPI do original e manifesto do que mudou. O original não é alterado.
        </p>
        {plan.data && plan.data.pending_critical > 0 && (
          <div className="warning small">
            Ainda há {plan.data.pending_critical} sinalização(ões) crítica(s) pendente(s). O lote corrigido
            leva essas páginas como estão e o manifesto as lista para retrabalho.
          </div>
        )}
        {plan.data && !plan.data.can_save && (
          <div className="blocked-reason small">
            Decida a página faltando antes de salvar: {plan.data.blockers.map((b) => b.document).join(", ")}.
          </div>
        )}
        <div className="row wrap">
          {folderExport && (
            <button
              className="primary"
              disabled={!plan.data?.can_save || saveToFolder.isPending}
              onClick={() => saveToFolder.mutate()}
            >
              {saveToFolder.isPending ? "Gravando o lote…" : "Salvar na pasta de saída"}
            </button>
          )}
          {(canDownload || !folderExport) && (
            <button
              className={folderExport ? "" : "primary"}
              disabled={!plan.data?.can_save || saveCorrected.isPending}
              onClick={() => saveCorrected.mutate()}
            >
              {saveCorrected.isPending ? "Gerando o lote…" : "Baixar lote corrigido (.zip)"}
            </button>
          )}
        </div>
        <ErrorBox error={saveToFolder.error ?? saveCorrected.error} />
        {[saveToFolder.data, saveCorrected.data].map(
          (saved) =>
            saved && (
              <p key={saved.file} className="small muted">
                {saved.totals.exported} páginas exportadas, {saved.totals.removed} removida(s),{" "}
                {saved.totals.corrected} corrigida(s).{" "}
                {saved.folder ? (
                  <>Gravado em <code>{saved.folder}</code>.</>
                ) : (
                  <>SHA-256 do zip: <code>{saved.sha256.slice(0, 16)}…</code></>
                )}
              </p>
            ),
        )}
      </Card>

      <Card title="Exportar">
        <div className="row wrap">
          {FILES.map(([name, label]) => (
            <button key={name} onClick={() => void get(name)}>{label}</button>
          ))}
        </div>
        <ErrorBox error={exports.error} />
      </Card>

      {sourceDefects.length > 0 && (
        <Card title="Defeitos de origem (para o cliente)">
          <ul className="plain">
            {sourceDefects.map((f) => <li key={f.id}>{ruleLabel(f.rule)}: {f.message}</li>)}
          </ul>
        </Card>
      )}

      <h2>Ordem de retrabalho</h2>
      {rework.isLoading && <Loading />}
      <ErrorBox error={rework.error} />
      {rework.data?.length === 0 && <p className="muted">Nenhuma ação física pendente.</p>}
      {[...byStation.entries()].map(([station, items]) => (
        <Card key={station} title={station}>
          <table className="table">
            <thead><tr><th>Caixa</th><th>Documento</th><th>Folha</th><th>O que fazer</th><th>Configuração</th></tr></thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.finding_id}>
                  <td>{i.box}</td>
                  <td>{i.document}</td>
                  <td>{i.page_position}</td>
                  <td><strong>{ruleLabel(i.rule ?? "")}</strong> — {i.instruction}</td>
                  <td className="small">{settings(i.settings)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  );
}
