import { useState, useSyncExternalStore } from "react";
import { getSession, logout, onSessionChange, type Health } from "./api/client";
import { EngineContext, hasCapability } from "./api/engine";
import { href, useRoute, type Route } from "./router";
import { Batch } from "./screens/Batch";
import { Boot } from "./screens/Boot";
import { Home } from "./screens/Home";
import { Login } from "./screens/Login";
import { Metadata } from "./screens/Metadata";
import { Profiles } from "./screens/Profiles";
import { Reports } from "./screens/Reports";
import { Review } from "./screens/Review";
import { Sequence } from "./screens/Sequence";
import { Settings } from "./screens/Settings";
import { Diagnostics } from "./screens/Diagnostics";
import { ErrorBoundary } from "./components/ErrorBoundary";

function useSession() {
  return useSyncExternalStore(onSessionChange, getSession);
}

export function App() {
  const [engine, setEngine] = useState<Health | null>(null);
  if (!engine) return <Boot onReady={setEngine} />;
  return (
    <EngineContext.Provider value={engine}>
      <Shell engine={engine} />
    </EngineContext.Provider>
  );
}

function Shell({ engine }: { engine: Health }) {
  const route = useRoute();
  const session = useSession();
  const osSession = hasCapability(engine, "os_session");
  const ready = Boolean(session.reviewer) && (!engine.auth_required || Boolean(session.token));
  if (!ready) return <Login engine={engine} />;
  const batchId = "id" in route ? route.id : null;

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href={href({ name: "home" })}>QA de Digitalização</a>
        {batchId && (
          <nav aria-label="Lote">
            <NavLink route={{ name: "batch", id: batchId }} current={route}>Painel</NavLink>
            <NavLink route={{ name: "review", id: batchId }} current={route}>Revisão</NavLink>
            <NavLink route={{ name: "sequence", id: batchId }} current={route}>Sequência</NavLink>
            <NavLink route={{ name: "metadata", id: batchId }} current={route}>Metadados</NavLink>
            <NavLink route={{ name: "reports", id: batchId }} current={route}>Relatório</NavLink>
          </nav>
        )}
        <div className="topbar-right">
          {hasCapability(engine, "settings") ? (
            <a href={href({ name: "settings" })}>Configurações</a>
          ) : (
            <a href={href({ name: "profiles" })}>Perfis</a>
          )}
          {engine.admin && <a href={href({ name: "diagnostics" })}>Diagnóstico</a>}
          <span className="muted reviewer-name">{session.reviewer}</span>
          {!osSession && <button className="link" onClick={logout}>{session.token ? "Sair" : "Trocar"}</button>}
        </div>
      </header>
      <ErrorBoundary key={route.name}>
        <Screen route={route} />
      </ErrorBoundary>
    </div>
  );
}

function NavLink({ route, current, children }: { route: Route; current: Route; children: React.ReactNode }) {
  return (
    <a href={href(route)} className={route.name === current.name ? "active" : ""} aria-current={route.name === current.name ? "page" : undefined}>
      {children}
    </a>
  );
}

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case "home":
    case "login":
      return <Home />;
    case "profiles":
      return <Profiles />;
    case "settings":
      return <Settings />;
    case "diagnostics":
      return <Diagnostics />;
    case "batch":
      return <Batch id={route.id} />;
    case "review":
      return <Review id={route.id} />;
    case "sequence":
      return <Sequence id={route.id} doc={route.doc} />;
    case "metadata":
      return <Metadata id={route.id} doc={route.doc} />;
    case "reports":
      return <Reports id={route.id} />;
  }
}
