// Partida: espera o motor responder antes de qualquer outra chamada. No plano gratuito
// do Render o motor dorme e a primeira chamada falha enquanto ele acorda (até ~1 min);
// sem esta espera, o celular mostrava "Failed to fetch".
import { useCallback, useEffect, useState } from "react";
import { DEFAULT_BASE, getSession, health, setSession, type Health } from "../api/client";
import { adoptEngineSession } from "../lib/session";
import { waitForEngine } from "../lib/wake";

type State =
  | { phase: "waiting"; attempt: number; elapsedMs: number }
  | { phase: "failed"; message: string };

export function Boot({ onReady }: { onReady: (engine: Health) => void }) {
  const [state, setState] = useState<State>({ phase: "waiting", attempt: 0, elapsedMs: 0 });
  const [base, setBase] = useState(getSession().base);
  const [run, setRun] = useState(0);

  const start = useCallback(() => setRun((n) => n + 1), []);

  useEffect(() => {
    const ctrl = new AbortController();
    setState({ phase: "waiting", attempt: 0, elapsedMs: 0 });
    waitForEngine(() => health(), {
      signal: ctrl.signal,
      onAttempt: (attempt, elapsedMs) => !ctrl.signal.aborted && setState({ phase: "waiting", attempt, elapsedMs }),
    })
      .then(async (engine) => {
        await adoptEngineSession(engine);
        if (!ctrl.signal.aborted) onReady(engine);
      })
      .catch((err: unknown) => !ctrl.signal.aborted && setState({ phase: "failed", message: err instanceof Error ? err.message : String(err) }));
    return () => ctrl.abort();
  }, [run, onReady]);

  const session = getSession();
  const where = session.base || window.location.origin;
  if (state.phase === "waiting") {
    const waking = state.attempt > 0;
    return (
      <div className="login">
        <div className="card login-card boot" role="status" aria-live="polite">
          <h1>QA de Digitalização</h1>
          <div className="spinner" aria-hidden="true" />
          <p>{waking ? "Acordando o motor de análise…" : "Conectando ao motor de análise…"}</p>
          {waking && (
            <p className="muted small">
              {Math.round(state.elapsedMs / 1000)} s · no plano gratuito do servidor, a primeira abertura do dia leva até 1 minuto.
            </p>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="login">
      <div className="card login-card boot">
        <h1>Não foi possível falar com o motor</h1>
        <div className="error" role="alert">{state.message}</div>
        <p className="small muted">Endereço usado: <code>{where}</code></p>
        <button className="primary" onClick={start}>Tentar de novo</button>
        {session.base !== DEFAULT_BASE && (
          <button
            onClick={() => {
              setSession({ ...session, base: DEFAULT_BASE });
              setBase(DEFAULT_BASE);
              start();
            }}
          >
            Usar o endereço padrão da publicação
          </button>
        )}
        <details>
          <summary>Trocar o endereço do motor</summary>
          <form
            className="row tight"
            onSubmit={(e) => {
              e.preventDefault();
              setSession({ ...session, base });
              start();
            }}
          >
            <input value={base} onChange={(e) => setBase(e.target.value)} aria-label="Endereço do motor" placeholder="https://qa-motor.onrender.com" />
            <button>Usar</button>
          </form>
        </details>
      </div>
    </div>
  );
}
