// Gestão: caixas concluídas por conferente, com o estado das pendências, de todas as máquinas.
// Sem tempo por caixa nem ranking de conferentes (decisão de produto; só entra por ADR).
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, download } from "../api/client";
import type { components } from "../api/schema";
import { Card, ErrorBox, Loading, Stat } from "../components/ui";
import { periodLabel, periodRange, type PeriodKind } from "../lib/period";

type View = components["schemas"]["management.schema"];
type Box = View["reviewers"][number]["items"][number];

const STATE: Record<Box["state"], string> = {
  clean: "Sem pendência",
  pending: "Com pendência",
  resolved: "Pendência resolvida",
};
const KINDS: [PeriodKind, string][] = [["day", "Dia"], ["week", "Semana"], ["month", "Mês"]];

export function Management() {
  const [kind, setKind] = useState<PeriodKind>("month");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const period = periodRange(kind, new Date(), offset);
  const query = new URLSearchParams({ since: period.since.toISOString(), until: period.until.toISOString() });
  const view = useQuery({
    queryKey: ["management", query.toString()],
    queryFn: () => api<View>(`/management?${query.toString()}`),
  });

  return (
    <div className="page">
      <h1>Gestão</h1>
      <div className="row wrap">
        <div className="segmented" role="group" aria-label="Período">
          {KINDS.map(([k, label]) => (
            <button key={k} className={k === kind ? "active" : ""} aria-pressed={k === kind} onClick={() => { setKind(k); setOffset(0); }}>
              {label}
            </button>
          ))}
        </div>
        <button onClick={() => setOffset(offset - 1)} aria-label="Período anterior">←</button>
        <strong>{periodLabel(kind, period)}</strong>
        <button onClick={() => setOffset(offset + 1)} disabled={offset >= 0} aria-label="Próximo período">→</button>
      </div>
      {view.isLoading && <Loading />}
      <ErrorBox error={view.error} />
      {view.data && <Body view={view.data} open={open} setOpen={setOpen} />}
    </div>
  );
}

function Body({ view, open, setOpen }: { view: View; open: string | null; setOpen: (v: string | null) => void }) {
  return (
    <>
      {!view.source.shared && (
        <p className="warning small">
          A pasta compartilhada de relatórios (<code>reports_dir</code>) não está configurada: aparecem só as caixas
          deste computador. Peça à TI para configurar e ver todas as máquinas.
        </p>
      )}
      {view.source.skipped > 0 && (
        <p className="small muted">{view.source.skipped} arquivo(s) da pasta compartilhada não puderam ser lidos e ficaram de fora.</p>
      )}
      <div className="stats">
        <Stat label="Caixas concluídas" value={view.totals.boxes} />
        <Stat label="Caixas com pendência" value={view.totals.boxes_pending} tone={view.totals.boxes_pending ? "warn" : undefined} />
        <Stat label="Processos" value={view.totals.processes} />
        <Stat label="Páginas" value={view.totals.pages} />
      </div>

      <Card title="Por conferente">
        {view.reviewers.length === 0 && <p className="muted">Nenhuma caixa concluída neste período.</p>}
        {view.reviewers.map((r) => (
          <details key={r.reviewer} className="reviewer-group">
            <summary>
              <strong>{r.reviewer}</strong> — {r.boxes} caixa(s), {r.pages} página(s)
            </summary>
            <table className="table">
              <thead>
                <tr><th>Caixa</th><th>Lote</th><th>Estado</th><th>Processos</th><th>Páginas</th><th>Concluída</th><th /></tr>
              </thead>
              <tbody>
                {r.items.map((b) => {
                  const key = `${r.reviewer}-${b.ref}`;
                  return (
                    <BoxRow key={key} box={b} expanded={open === key} toggle={() => setOpen(open === key ? null : key)} />
                  );
                })}
              </tbody>
            </table>
          </details>
        ))}
      </Card>

      <Card title="Versão do programa em cada máquina">
        <p className="small muted">
          A versão é a da última abertura do programa em cada máquina. Estação marcada como desatualizada está numa
          versão anterior à mais nova em uso.
        </p>
        <table className="table">
          <thead><tr><th>Máquina</th><th>Versão</th><th>Última abertura</th><th>Último relatório</th></tr></thead>
          <tbody>
            {view.machines.map((m) => (
              <tr key={m.machine}>
                <td>{m.machine}</td>
                <td>
                  <code>{m.program_version || "—"}</code>
                  {m.outdated && <> <span className="tag warn">desatualizada</span></>}
                </td>
                <td>{when(m.last_seen_at)}</td>
                <td>{when(m.last_report_at)}</td>
              </tr>
            ))}
            {view.machines.length === 0 && <tr><td colSpan={4} className="muted">Nenhuma máquina ainda.</td></tr>}
          </tbody>
        </table>
      </Card>
    </>
  );
}

function BoxRow({ box, expanded, toggle }: { box: Box; expanded: boolean; toggle: () => void }) {
  return (
    <>
      <tr onClick={toggle} style={{ cursor: "pointer" }} aria-expanded={expanded}>
        <td>{box.box}</td>
        <td className="small">{box.batch_name}<div className="muted">{box.machine}</div></td>
        <td>
          <span className={`tag ${box.state === "pending" ? "warn" : ""}`}>{STATE[box.state]}</span>
          {box.versions > 1 && <div className="small muted">v{box.version} de {box.versions}</div>}
        </td>
        <td>{box.totals.processes}</td>
        <td>{box.totals.pages}</td>
        <td className="small">{new Date(box.concluded_at).toLocaleString("pt-BR")}</td>
        <td>
          <button
            className="small-btn"
            onClick={(e) => {
              e.stopPropagation();
              void download(`/management/report.pdf?ref=${encodeURIComponent(box.ref)}`, `${box.box}-v${box.version}.pdf`);
            }}
          >
            Abrir relatório
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7}>
            <table className="table small">
              <thead><tr><th>Processo</th><th>Páginas</th><th>Faltando</th><th>Ilegíveis</th></tr></thead>
              <tbody>
                {box.processes.map((p) => (
                  <tr key={p.number}>
                    <td>{p.number}</td>
                    <td>{p.pages}</td>
                    <td>{p.clean ? "—" : p.missing}</td>
                    <td>{p.clean ? "Nenhuma pendência" : p.illegible}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}

/** Data e hora locais; vazio vira travessão. */
function when(iso: string | undefined): string {
  return iso ? new Date(iso).toLocaleString("pt-BR") : "—";
}
