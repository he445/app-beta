// Diagnóstico (só com token de administrador): erros de todas as máquinas, agrupados.
// O token fica só na memória desta aba; nunca vai para o armazenamento do navegador.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, raw } from "../api/client";
import type { components } from "../api/schema";
import { Card, ErrorBox, Loading, Stat } from "../components/ui";

type S = components["schemas"];
type DiagnosticsBody = S["diagnostics.schema"];
type Group = S["diagnostic-group.schema"];
type Detail = S["diagnostic-detail.schema"];
type Day = DiagnosticsBody["summary"]["per_day"][number];

const SEVERITY: Record<Group["severity"], string> = { critical: "Crítico", error: "Erro", warning: "Aviso" };
const ORIGIN: Record<Group["origin"], string> = {
  engine: "Motor",
  worker: "Processo de análise",
  startup: "Abertura do programa",
  client: "Interface",
};
const COLORS: Record<Group["severity"], string> = { critical: "var(--critical)", error: "var(--high)", warning: "var(--medium)" };

let memoryToken = "";

async function admin<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const res = await raw(path, { ...init, headers: { "X-Admin-Token": token } });
  return (await res.json()) as T;
}

export function Diagnostics() {
  const [token, setToken] = useState(memoryToken);
  const [typed, setTyped] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({ status: "open" });
  const [selected, setSelected] = useState<string | null>(null);
  const qc = useQueryClient();
  const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();

  const list = useQuery({
    queryKey: ["diagnostics", token, query],
    queryFn: () => admin<DiagnosticsBody>(`/admin/diagnostics${query ? `?${query}` : ""}`, token),
    enabled: Boolean(token),
    retry: false,
  });
  const detail = useQuery({
    queryKey: ["diagnostic", token, selected],
    queryFn: () => admin<Detail>(`/admin/diagnostics/${selected}`, token),
    enabled: Boolean(token && selected),
  });
  const resolve = useMutation({
    mutationFn: (signature: string) => admin<Detail>(`/admin/diagnostics/${signature}/resolve`, token, { method: "POST" }),
    onSuccess: (next) => {
      qc.setQueryData(["diagnostic", token, next.group.signature], next);
      void qc.invalidateQueries({ queryKey: ["diagnostics"] });
    },
  });
  const exportPackage = useMutation({
    mutationFn: async () => {
      const res = await raw("/admin/diagnostics/export", { headers: { "X-Admin-Token": token } });
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? "diagnostico.zip";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    },
  });

  const refused = list.error instanceof ApiError && list.error.status === 401;
  if (!token || refused) {
    return (
      <div className="page">
        <h1>Diagnóstico</h1>
        <form
          className="card login-card"
          onSubmit={(e) => {
            e.preventDefault();
            memoryToken = typed.trim();
            setToken(memoryToken);
          }}
        >
          <p className="muted small">Área de administração. O token é gerado com <code>qa admin token</code> e fica só nesta aba.</p>
          <label>
            Token de administrador
            <input type="password" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" required />
          </label>
          {refused && <div className="error" role="alert">Token recusado.</div>}
          {list.error && !refused && <ErrorBox error={list.error} />}
          <button className="primary">Entrar</button>
        </form>
      </div>
    );
  }
  if (list.isLoading) return <Loading />;
  if (!list.data) return <div className="page"><ErrorBox error={list.error} /></div>;
  const { summary, groups, filters: options } = list.data;

  return (
    <div className="page">
      <h1>Diagnóstico</h1>
      <div className="stats">
        <Stat label="Erros nas últimas 24 h" value={summary.last_24h} />
        <Stat label="Erros em 7 dias" value={summary.last_7d} />
        <Stat label="Máquinas afetadas (7 dias)" value={summary.machines} />
        <Stat label="Erros abertos" value={summary.open} tone={summary.open ? "bad" : undefined} />
      </div>

      <Card title="Erros por dia (30 dias)">
        <DayChart days={summary.per_day} />
      </Card>

      <Card>
        <div className="row wrap">
          <Select label="Versão" value={filters.version} options={options.versions} onChange={(v) => setFilters({ ...filters, version: v })} />
          <Select label="Máquina" value={filters.machine} options={options.machines} onChange={(v) => setFilters({ ...filters, machine: v })} />
          <Select label="Gravidade" value={filters.severity} options={Object.keys(SEVERITY)} labels={SEVERITY} onChange={(v) => setFilters({ ...filters, severity: v })} />
          <Select label="Estado" value={filters.status} options={["open", "resolved"]} labels={{ open: "Abertos", resolved: "Resolvidos" }} onChange={(v) => setFilters({ ...filters, status: v })} />
          <button onClick={() => exportPackage.mutate()} disabled={exportPackage.isPending}>
            {exportPackage.isPending ? "Exportando…" : "Exportar pacote"}
          </button>
        </div>
        <ErrorBox error={exportPackage.error} />
        <table className="table">
          <thead>
            <tr><th>Erro</th><th>Gravidade</th><th>Onde</th><th>Vezes</th><th>Máquinas e versões</th><th>Primeira / última</th></tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.signature} className={g.signature === selected ? "selected" : ""} onClick={() => setSelected(g.signature)} style={{ cursor: "pointer" }}>
                <td>
                  <strong>{g.kind}</strong>
                  <div className="small">{g.message}</div>
                  <div className="small muted"><code>{g.location}</code></div>
                </td>
                <td><span className="badge" style={{ background: COLORS[g.severity] }}>{SEVERITY[g.severity]}</span></td>
                <td className="small">{ORIGIN[g.origin]}</td>
                <td>{g.count}</td>
                <td className="small">{g.machines.join(", ")}<div className="muted">{g.versions.join(", ")}</div></td>
                <td className="small">{when(g.first_at)}<div className="muted">{when(g.last_at)}</div></td>
              </tr>
            ))}
            {groups.length === 0 && <tr><td colSpan={6} className="muted">Nenhum erro com esses filtros.</td></tr>}
          </tbody>
        </table>
      </Card>

      {selected && (
        <Card title="Detalhe">
          {detail.isLoading && <Loading />}
          <ErrorBox error={detail.error} />
          {detail.data && (
            <>
              <p>
                <strong>{detail.data.group.kind}</strong> em <code>{detail.data.group.location}</code> ·{" "}
                {detail.data.group.status === "resolved" ? `resolvido por ${detail.data.group.resolved_by}` : "aberto"}
              </p>
              {detail.data.group.status === "open" && (
                <button className="primary" disabled={resolve.isPending} onClick={() => resolve.mutate(detail.data!.group.signature)}>
                  Marcar como resolvido
                </button>
              )}
              <h3>Pilha de chamadas (ocorrência mais recente)</h3>
              <pre className="code small">{detail.data.occurrences.at(-1)?.stack}</pre>
              <h3>Linha do tempo</h3>
              <table className="table small">
                <thead><tr><th>Quando</th><th>Máquina</th><th>Versão</th><th>Usuário</th><th>Tela ou rota</th></tr></thead>
                <tbody>
                  {[...detail.data.occurrences].reverse().map((o) => (
                    <tr key={o.id ?? o.at}>
                      <td>{when(o.at ?? "")}</td>
                      <td>{o.machine}</td>
                      <td>{o.version}</td>
                      <td>{o.user ?? "—"}</td>
                      <td><code>{o.where ?? "—"}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </Card>
      )}
    </div>
  );
}

function when(iso: string): string {
  return iso ? new Date(iso).toLocaleString("pt-BR") : "—";
}

function Select({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: string | undefined;
  options: string[];
  labels?: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        <option value="">Todos</option>
        {options.map((o) => (
          <option key={o} value={o}>{labels?.[o] ?? o}</option>
        ))}
      </select>
    </label>
  );
}

/** Barras empilhadas por gravidade, uma por dia (SVG simples, sem biblioteca). */
function DayChart({ days }: { days: Day[] }) {
  const max = Math.max(1, ...days.map((d) => d.critical + d.error + d.warning));
  const width = 600;
  const height = 120;
  const bar = width / days.length;
  return (
    <svg viewBox={`0 0 ${width} ${height + 18}`} role="img" aria-label="Erros por dia, por gravidade" style={{ width: "100%", maxWidth: 720 }}>
      {days.map((d, i) => {
        let y = height;
        return (
          <g key={d.day}>
            <title>{`${d.day}: ${d.critical} crítico(s), ${d.error} erro(s), ${d.warning} aviso(s)`}</title>
            {(["warning", "error", "critical"] as const).map((s) => {
              const h = (d[s] / max) * height;
              y -= h;
              return h > 0 ? <rect key={s} x={i * bar + 1} y={y} width={bar - 2} height={h} fill={COLORS[s]} /> : null;
            })}
          </g>
        );
      })}
      <line x1={0} y1={height} x2={width} y2={height} stroke="currentColor" opacity={0.3} />
      <text x={0} y={height + 14} fontSize={11} fill="currentColor" opacity={0.7}>{days[0]?.day}</text>
      <text x={width} y={height + 14} fontSize={11} fill="currentColor" opacity={0.7} textAnchor="end">{days.at(-1)?.day}</text>
    </svg>
  );
}
