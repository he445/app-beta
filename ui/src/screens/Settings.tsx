// Configurações (capacidade "settings"): ajustes das digitalizadoras por perfil e estação, e
// deste computador. Cada valor mostra de onde veio; valor inválido é recusado antes de salvar.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ApiError, api, json, raw } from "../api/client";
import { useEngine } from "../api/engine";
import { keys, useProfiles } from "../api/hooks";
import type { components } from "../api/schema";
import type { ParamView, Profile, RuleView, SettingsView } from "../api/types";
import { Card, ErrorBox, Loading } from "../components/ui";
import { ruleLabel } from "../lib/format";
import { useAdminToken } from "../lib/useAdminToken";
import {
  LAYER_LABEL,
  formatComputerField,
  parseComputerField,
  parseParam,
  withRuleChange,
} from "../lib/settings";

type Tab = "scanners" | "computer";

export function Settings() {
  const [tab, setTab] = useState<Tab>("scanners");
  return (
    <div className="page">
      <h1>Configurações</h1>
      <div className="row tight" role="tablist" aria-label="Configurações">
        <button role="tab" aria-selected={tab === "scanners"} className={tab === "scanners" ? "primary" : ""} onClick={() => setTab("scanners")}>
          Digitalizadoras
        </button>
        <button role="tab" aria-selected={tab === "computer"} className={tab === "computer" ? "primary" : ""} onClick={() => setTab("computer")}>
          Este computador
        </button>
      </div>
      {tab === "scanners" ? <ScannersTab /> : <ComputerTab />}
      <HistoryCard />
    </div>
  );
}

function Origin({ source }: { source: string }) {
  return <span className="muted small origin" title="De onde veio este valor">{LAYER_LABEL[source] ?? source}</span>;
}

// Digitalizadoras ----------------------------------------------------------------------

function ScannersTab() {
  const profiles = useProfiles();
  const qc = useQueryClient();
  const [profileId, setProfileId] = useState("");
  const [stationId, setStationId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string | boolean>>({});
  const list = profiles.data ?? [];
  const profile = list.find((p) => p.id === profileId) ?? list.find((p) => p.id === "sos-piloto") ?? list[0];
  const stations = (profile?.stations ?? []).filter((s) => s.id);
  const level = stationId || null;

  const rules = useQuery({
    queryKey: ["profile-rules", profile?.id, stationId],
    queryFn: () =>
      api<RuleView[]>(`/profiles/${profile!.id}/rules${stationId ? `?station_id=${encodeURIComponent(stationId)}` : ""}`),
    enabled: Boolean(profile),
  });

  useEffect(() => setDrafts({}), [profile?.id, stationId]);

  const engine = useEngine();
  const [token, setToken] = useAdminToken();
  const [typed, setTyped] = useState("");
  const locked = !token;
  const save = useMutation({
    mutationFn: async (next: Profile) => {
      const res = await raw(`/profiles/${next.id}`, {
        method: "PUT",
        body: JSON.stringify(next),
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
      });
      return (await res.json()) as Profile;
    },
    onSuccess: () => {
      setDrafts({});
      void qc.invalidateQueries({ queryKey: keys.profiles });
      void qc.invalidateQueries({ queryKey: ["profile-rules"] });
      void qc.invalidateQueries({ queryKey: ["config-history"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 401) setToken("");
    },
  });

  const parsed = useMemo(() => {
    const result: Record<string, { rule: string; param: ParamView; value: unknown; error: string | null }> = {};
    for (const rule of rules.data ?? []) {
      for (const param of rule.params) {
        const key = `${rule.rule}.${param.name}`;
        if (!(key in drafts)) continue;
        const { value, error } = parseParam(param, drafts[key]!);
        result[key] = { rule: rule.rule, param, value, error };
      }
    }
    return result;
  }, [drafts, rules.data]);
  const errors = Object.values(parsed).filter((p) => p.error);

  function apply(change: (p: Profile) => Profile) {
    if (profile) save.mutate(change(profile));
  }

  function saveDrafts() {
    if (!profile || errors.length) return;
    let next = profile;
    for (const { rule, param, value } of Object.values(parsed)) {
      next = withRuleChange(next, level, rule, { param: param.name, value });
    }
    save.mutate(next);
  }

  if (profiles.isLoading) return <Loading />;
  return (
    <>
      {locked && (
        <Card>
          {engine.admin ? (
            <form
              className="row wrap"
              onSubmit={(e) => {
                e.preventDefault();
                setToken(typed);
                setTyped("");
              }}
            >
              <span className="small">
                Ajustes das digitalizadoras, limites e perfis exigem o <strong>token de administrador</strong>. Sem ele, os
                campos ficam bloqueados.
              </span>
              <label>
                Token de administrador
                <input type="password" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" required />
              </label>
              <button className="primary">Destravar</button>
            </form>
          ) : (
            <p className="small">
              Ajustes das digitalizadoras, limites e perfis exigem o token de administrador, que ainda não foi gerado neste
              computador. A TI gera com <code>QA-suporte.exe admin token</code>.
            </p>
          )}
        </Card>
      )}
      <Card>
        <p className="small muted">
          Ordem de aplicação de cada valor: padrão da regra → perfil → estação. Mudar aqui grava no perfil;
          o que já foi analisado continua explicado pelo perfil da época.
        </p>
        <div className="row wrap">
          <label>
            Perfil
            <select value={profile?.id ?? ""} onChange={(e) => setProfileId(e.target.value)}>
              {list.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
          <label>
            Ajustar para
            <select value={stationId} onChange={(e) => setStationId(e.target.value)}>
              <option value="">O perfil inteiro</option>
              {stations.map((s) => (
                <option key={s.id} value={s.id!}>{s.location}{s.model ? ` (${s.make ?? ""} ${s.model})` : ""}</option>
              ))}
            </select>
          </label>
        </div>
      </Card>
      {rules.isLoading && <Loading />}
      <ErrorBox error={rules.error} />
      {rules.data?.map((rule) => (
        <Card key={rule.rule} title={ruleLabel(rule.rule)}>
          <label className="row tight">
            <input
              type="checkbox"
              checked={rule.enabled}
              disabled={locked || save.isPending}
              onChange={(e) => apply((p) => withRuleChange(p, level, rule.rule, { enabled: e.target.checked }))}
            />
            Ligada <Origin source={rule.enabled_source} />
            {!locked && rule.enabled_source === (level ? "station" : "profile") && (
              <button className="link small" onClick={() => apply((p) => withRuleChange(p, level, rule.rule, { enabled: undefined }))}>
                voltar ao herdado
              </button>
            )}
          </label>
          {rule.params.length > 0 && (
            <table className="table">
              <thead>
                <tr><th>Parâmetro</th><th>Valor</th><th>Origem</th><th>Padrão da regra</th></tr>
              </thead>
              <tbody>
                {rule.params.map((param) => {
                  const key = `${rule.rule}.${param.name}`;
                  const draft = drafts[key];
                  const error = parsed[key]?.error;
                  const own = param.source === (level ? "station" : "profile");
                  return (
                    <tr key={key}>
                      <td>
                        <code>{param.name}</code>
                        {param.description && <div className="small muted">{param.description}</div>}
                      </td>
                      <td>
                        {param.type === "boolean" ? (
                          <input
                            type="checkbox"
                            aria-label={param.name}
                            checked={Boolean(draft ?? param.value)}
                            disabled={locked}
                            onChange={(e) => setDrafts({ ...drafts, [key]: e.target.checked })}
                          />
                        ) : (
                          <input
                            aria-label={param.name}
                            aria-invalid={Boolean(error)}
                            inputMode="decimal"
                            disabled={locked}
                            value={String(draft ?? param.value)}
                            onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })}
                          />
                        )}
                        {error && <div className="error small" role="alert">{error}</div>}
                      </td>
                      <td>
                        <Origin source={param.source} />
                        {own && !locked && (
                          <button
                            className="link small"
                            onClick={() => apply((p) => withRuleChange(p, level, rule.rule, { param: param.name, value: undefined }))}
                          >
                            voltar ao herdado
                          </button>
                        )}
                      </td>
                      <td className="small">{String(param.default)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      ))}
      {Object.keys(drafts).length > 0 && (
        <div className="row wrap sticky-actions">
          <button className="primary" disabled={errors.length > 0 || save.isPending} onClick={saveDrafts}>
            {save.isPending ? "Salvando…" : `Salvar ${Object.keys(drafts).length} mudança(s) ${level ? "nesta estação" : "no perfil"}`}
          </button>
          <button onClick={() => setDrafts({})}>Descartar</button>
          {errors.length > 0 && <span className="error small">Corrija os valores marcados antes de salvar.</span>}
        </div>
      )}
      <ErrorBox error={save.error} />
    </>
  );
}

// Este computador --------------------------------------------------------------------

const COMPUTER_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: "output_dir", label: "Pasta de saída", hint: "Onde vai o lote corrigido. Vazio = Documentos\\QA\\Saída." },
  { key: "allowed_roots", label: "Pastas permitidas", hint: "Uma por linha. Vazio = qualquer pasta que você consiga ler." },
  { key: "default_station", label: "Estação padrão", hint: "Usada quando o arquivo não diz de qual digitalizadora veio." },
  { key: "batch_settle_seconds", label: "Espera da pasta (s)", hint: "Tempo sem nenhum arquivo mudar antes de analisar." },
  { key: "workers", label: "Processos de análise", hint: "“auto” = núcleos − 1." },
  { key: "max_memory_mb", label: "Teto de memória (MB)", hint: "“auto” = metade da memória do computador." },
  { key: "retention_days", label: "Guardar cópias por (dias)", hint: "Miniaturas e cópias corrigidas." },
  { key: "log_level", label: "Detalhe do log", hint: "debug, info, warning ou error." },
  { key: "data_dir", label: "Pasta de dados", hint: "Banco, cópias e log. Mudar exige mover os dados." },
  { key: "temp_dir", label: "Pasta temporária", hint: "Vazio = dentro da pasta de dados." },
];

function ComputerTab() {
  const qc = useQueryClient();
  const profiles = useProfiles();
  const view = useQuery({ queryKey: ["settings"], queryFn: () => api<SettingsView>("/settings") });
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const save = useMutation({
    mutationFn: (body: { changes: Record<string, unknown>; reset: string[] }) => json<SettingsView>("/settings", "PUT", body),
    onSuccess: (next) => {
      void qc.invalidateQueries({ queryKey: ["config-history"] });
      setDrafts({});
      qc.setQueryData(["settings"], next);
    },
  });
  const stationIds = [...new Set((profiles.data ?? []).flatMap((p) => (p.stations ?? []).map((s) => s.id).filter(Boolean)))] as string[];

  if (view.isLoading) return <Loading />;
  if (!view.data) return <ErrorBox error={view.error} />;
  const data = view.data;
  const values = data.values as Record<string, unknown>;
  const serverProblems = save.error instanceof ApiError ? save.error.problems : [];
  const parsed = Object.fromEntries(Object.entries(drafts).map(([k, raw]) => [k, parseComputerField(k, raw)]));
  const hasErrors = Object.values(parsed).some((p) => p.error);

  function submit() {
    const changes: Record<string, unknown> = {};
    const reset: string[] = [];
    for (const [key, result] of Object.entries(parsed)) {
      if (result.value === null && ["output_dir", "temp_dir", "default_station"].includes(key)) reset.push(key);
      else changes[key] = result.value;
    }
    save.mutate({ changes, reset });
  }

  return (
    <Card>
      <p className="small muted">
        Seus ajustes ficam em <code>{data.files.user ?? "—"}</code>. O que a TI travou em{" "}
        <code>{data.files.machine ?? "—"}</code> aparece só para leitura.
      </p>
      {data.restart_required && (
        <div className="warning small" role="status">As mudanças salvas valem na próxima abertura do programa.</div>
      )}
      <table className="table">
        <thead>
          <tr><th>Configuração</th><th>Valor</th><th>Origem</th></tr>
        </thead>
        <tbody>
          {COMPUTER_FIELDS.map(({ key, label, hint }) => {
            const locked = data.locked.includes(key) || !data.editable.includes(key);
            const raw = drafts[key] ?? formatComputerField(key, values[key]);
            const error = parsed[key]?.error ?? serverProblems.find((p) => p.key === key)?.expected;
            const input =
              key === "allowed_roots" ? (
                <textarea rows={3} value={raw} disabled={locked} aria-label={label} onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })} />
              ) : key === "log_level" ? (
                <select value={raw} disabled={locked} aria-label={label} onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })}>
                  {["debug", "info", "warning", "error"].map((v) => <option key={v}>{v}</option>)}
                </select>
              ) : key === "default_station" ? (
                <select value={raw} disabled={locked} aria-label={label} onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })}>
                  <option value="">Nenhuma</option>
                  {stationIds.map((id) => <option key={id}>{id}</option>)}
                </select>
              ) : (
                <input value={raw} disabled={locked} aria-label={label} aria-invalid={Boolean(error)} spellCheck={false} onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })} />
              );
            return (
              <tr key={key}>
                <td>
                  <strong>{label}</strong>
                  <div className="small muted">{hint}</div>
                </td>
                <td>
                  {input}
                  {error && <div className="error small" role="alert">{error}</div>}
                </td>
                <td>
                  <Origin source={data.origins[key] ?? "default"} />
                  {data.locked.includes(key) && <div className="small muted">travado pela TI</div>}
                  {["env", "args"].includes(data.origins[key] ?? "") && (
                    <div className="small muted">sobreposto nesta abertura; o que você salvar vale sem ele</div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="row wrap">
        <button className="primary" disabled={!Object.keys(drafts).length || hasErrors || save.isPending} onClick={submit}>
          {save.isPending ? "Salvando…" : "Salvar"}
        </button>
        {Object.keys(drafts).length > 0 && <button onClick={() => setDrafts({})}>Descartar</button>}
        {hasErrors && <span className="error small">Corrija os valores marcados antes de salvar.</span>}
      </div>
      {save.error && !serverProblems.length && <ErrorBox error={save.error} />}
      {save.isSuccess && <div className="ok-box">Configuração salva.</div>}
    </Card>
  );
}

// Histórico ---------------------------------------------------------------------------

type Change = components["schemas"]["config-change.schema"];

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function HistoryCard() {
  const history = useQuery({ queryKey: ["config-history"], queryFn: () => api<Change[]>("/config-history?limit=100") });
  return (
    <Card title="Histórico de configuração">
      <p className="small muted">Toda mudança fica registrada: quem mudou, quando, o valor anterior e o novo. Vai também com cada lote.</p>
      <ErrorBox error={history.error} />
      <table className="table small">
        <thead><tr><th>Quando</th><th>Quem</th><th>O quê</th><th>Antes</th><th>Depois</th></tr></thead>
        <tbody>
          {(history.data ?? []).map((c) => (
            <tr key={c.id}>
              <td>{new Date(c.at).toLocaleString("pt-BR")}</td>
              <td>{c.who}</td>
              <td>
                <span className="muted">{c.scope === "profile" ? `perfil ${c.target}` : "este computador"}:</span> <code>{c.key}</code>
              </td>
              <td><code>{show(c.before)}</code></td>
              <td><code>{show(c.after)}</code></td>
            </tr>
          ))}
          {history.data?.length === 0 && <tr><td colSpan={5} className="muted">Nenhuma mudança registrada.</td></tr>}
        </tbody>
      </table>
    </Card>
  );
}
