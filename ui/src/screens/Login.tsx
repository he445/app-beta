import { useState } from "react";
import { getSession, setSession } from "../api/client";
import { navigate } from "../router";

export function Login() {
  const current = getSession();
  const [base, setBase] = useState(current.base);
  const [token, setToken] = useState("");
  const [reviewer, setReviewer] = useState(current.reviewer);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${base}/batches`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) throw new Error("Token recusado pelo motor.");
      if (!res.ok) throw new Error(`O motor respondeu ${res.status}.`);
      setSession({ base: base.replace(/\/$/, ""), token, reviewer: reviewer.trim() });
      navigate({ name: "home" });
    } catch (err) {
      setError(err instanceof TypeError ? "Não foi possível falar com o motor nesse endereço." : String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="card login-card" onSubmit={submit}>
        <h1>QA de Digitalização</h1>
        <p className="muted">Entre com o token de acesso ao motor de análise.</p>
        <label>
          Seu nome (registrado em cada decisão)
          <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} required autoComplete="name" />
        </label>
        <label>
          Token de acesso
          <input type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="current-password" />
        </label>
        <details>
          <summary>Endereço do motor</summary>
          <input value={base} onChange={(e) => setBase(e.target.value)} aria-label="Endereço do motor" />
        </details>
        {error && <div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={busy}>{busy ? "Conferindo…" : "Entrar"}</button>
      </form>
    </div>
  );
}
