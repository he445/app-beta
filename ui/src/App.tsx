import { useEffect, useSyncExternalStore } from "react";
import { getSession, logout, onSessionChange } from "./api/client";
import { href, navigate, useRoute, type Route } from "./router";
import { Batch } from "./screens/Batch";
import { Home } from "./screens/Home";
import { Login } from "./screens/Login";
import { Metadata } from "./screens/Metadata";
import { Profiles } from "./screens/Profiles";
import { Reports } from "./screens/Reports";
import { Review } from "./screens/Review";
import { Sequence } from "./screens/Sequence";

function useSession() {
  return useSyncExternalStore(onSessionChange, getSession);
}

export function App() {
  const route = useRoute();
  const session = useSession();
  const loggedIn = Boolean(session.token);

  useEffect(() => {
    if (!loggedIn && route.name !== "login") navigate({ name: "login" });
  }, [loggedIn, route.name]);

  if (!loggedIn || route.name === "login") return <Login />;
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
          <a href={href({ name: "profiles" })}>Perfis</a>
          <span className="muted">{session.reviewer}</span>
          <button className="link" onClick={logout}>Sair</button>
        </div>
      </header>
      <Screen route={route} />
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
