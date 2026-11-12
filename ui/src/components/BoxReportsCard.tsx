// Relatório por caixa: o que falta e o que está ilegível em cada processo, com as versões.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, download, getSession, json } from "../api/client";
import type { components } from "../api/schema";
import { Card, ErrorBox } from "./ui";

type BoxReport = components["schemas"]["box-report.schema"];
type Item = { id: string; report: BoxReport };

const STATE: Record<BoxReport["state"], string> = {
  clean: "Sem pendência",
  pending: "Com pendência",
  resolved: "Pendência resolvida",
};

/** Só a versão mais nova de cada caixa; as anteriores ficam guardadas. */
export function latestByBox(items: Item[]): Item[] {
  const latest = new Map<string, Item>();
  for (const item of items) {
    const current = latest.get(item.report.box);
    if (!current || item.report.version > current.report.version) latest.set(item.report.box, item);
  }
  return [...latest.values()].sort((a, b) => a.report.box.localeCompare(b.report.box, "pt-BR", { numeric: true }));
}

export function BoxReportsCard({ batchId, refreshKey }: { batchId: string; refreshKey: number }) {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["box-reports", batchId, refreshKey],
    queryFn: () => api<Item[]>(`/batches/${batchId}/box-reports`),
  });
  const generate = useMutation({
    mutationFn: () => json<Item[]>(`/batches/${batchId}/box-reports`, "POST", { reviewer: getSession().reviewer || "revisor" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["box-reports", batchId] }),
  });
  const items = latestByBox(list.data ?? []);
  return (
    <Card title="Relatórios por caixa">
      <p className="small muted">
        Saem quando todas as decisões da caixa foram tomadas (e ao salvar o lote corrigido): páginas faltando e
        páginas ilegíveis de cada processo, ou “Nenhuma pendência”. Se uma pendência mudar, sai uma versão nova e a
        anterior fica guardada.
      </p>
      <div className="row wrap">
        <button onClick={() => generate.mutate()} disabled={generate.isPending}>
          {generate.isPending ? "Gerando…" : "Gerar relatório das caixas concluídas"}
        </button>
        {generate.data && generate.data.length === 0 && (
          <span className="small muted">Nada novo: nenhuma caixa concluída mudou desde o último relatório.</span>
        )}
      </div>
      <ErrorBox error={list.error ?? generate.error} />
      {items.length > 0 && (
        <table className="table">
          <thead>
            <tr><th>Caixa</th><th>Versão</th><th>Estado</th><th>Processos</th><th>Faltando</th><th>Ilegíveis</th><th /></tr>
          </thead>
          <tbody>
            {items.map(({ id, report }) => (
              <tr key={id}>
                <td>{report.box}</td>
                <td>v{report.version}</td>
                <td><span className={`tag ${report.state === "pending" ? "warn" : ""}`}>{STATE[report.state]}</span></td>
                <td>{report.totals.processes}</td>
                <td>{report.totals.missing}</td>
                <td>{report.totals.illegible}</td>
                <td>
                  <button className="small-btn" onClick={() => void download(`/box-reports/${id}.pdf`, `${report.box}-v${report.version}.pdf`)}>
                    PDF
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
