// Tela quebrada: mostra um aviso em vez de uma página em branco e registra no diagnóstico.
import { Component, type ErrorInfo, type ReactNode } from "react";
import { reportError } from "../lib/report-error";

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    const enriched = new Error(error.message);
    enriched.name = error.name;
    enriched.stack = `${error.stack ?? ""}\nComponentes:${info.componentStack ?? ""}`;
    reportError(enriched, "RenderError");
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="page">
        <div className="error" role="alert">
          <strong>Algo deu errado nesta tela.</strong> O erro foi registrado para o suporte. Suas
          decisões já salvas não se perdem.
        </div>
        <button className="primary" onClick={() => window.location.reload()}>Recarregar</button>
      </div>
    );
  }
}
