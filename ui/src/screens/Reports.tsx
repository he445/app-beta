// Tela 8: relatório do lote e ordem de retrabalho por estação.
import { useMutation, useQuery } from "@tanstack/react-query";
import { raw, download } from "../api/client";
import { useReport } from "../api/hooks";
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
