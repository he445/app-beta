// Entrada. Na demonstração (motor sem QA_API_TOKEN) pede só o nome do revisor, que fica
// gravado em cada decisão. O modo com token continua aqui, dormente: liga sozinho
// quando o motor informa ``auth_required`` em ``GET /health`` (ADR-0010).
import { useState } from "react";
import { getSession, setSession, type Health } from "../api/client";

export function Login({ engine }: { engine: Health }) {
  const current = getSession();
  const [reviewer, setReviewer] = useState(current.reviewer);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const needsToken = engine.auth_required;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const name = reviewer.trim();
    if (!name) return;
    if (!needsToken) {
      setSession({ ...current, token: "", reviewer: name });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${current.base}/batches`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) throw new Error("Token recusado pelo motor.");
      if (!res.ok) throw new Error(`O motor respondeu ${res.status}.`);
      setSession({ ...current, token, reviewer: name });
    } catch (err) {
      setError(err instanceof TypeError ? "Não foi possível falar com o motor." : String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="card login-card" onSubmit={submit}>
        <h1>QA de Digitalização</h1>
        <p className="muted">Seu nome fica registrado em cada decisão de revisão.</p>
        <label>
          Seu nome
          <input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            required
            autoFocus
            autoComplete="name"
            enterKeyHint="go"
            placeholder="Ex.: Maria (garantidora)"
          />
        </label>
        {needsToken && (
          <label>
            Token de acesso
            <input type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="current-password" required />
          </label>
        )}
        {error && <div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={busy || !reviewer.trim()}>
          {busy ? "Conferindo…" : "Começar"}
        </button>
      </form>
    </div>
  );
}
