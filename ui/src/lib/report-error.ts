// Erros da interface vão para o diagnóstico do motor, sem imagem nem texto de documento.
import { json } from "../api/client";

const MAX_PER_MESSAGE = 5;
const seen = new Map<string, number>();

/** Rota da tela sem identificadores: "#/batches/:id/review". */
export function screenOf(hash: string): string {
  return hash.replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, ":id").replace(/\?.*$/, "") || "#/";
}

/** Manda um erro ao motor (no máximo 5 vezes a mesma mensagem por aba; falha é ignorada). */
export function reportError(error: unknown, kind = "Error"): void {
  const err = error instanceof Error ? error : new Error(String(error));
  const key = `${err.name}:${err.message}`;
  const count = seen.get(key) ?? 0;
  if (count >= MAX_PER_MESSAGE) return;
  seen.set(key, count + 1);
  const body = {
    kind: err.name || kind,
    message: err.message.slice(0, 2000),
    stack: (err.stack ?? "").slice(0, 20000),
    screen: screenOf(typeof window === "undefined" ? "" : window.location.hash),
  };
  void json("/diagnostics/client-errors", "POST", body).catch(() => undefined);
}

/** Liga a captura de erros não tratados da página. */
export function installErrorReporting(): void {
  window.addEventListener("error", (event) => reportError(event.error ?? event.message, "Error"));
  window.addEventListener("unhandledrejection", (event) => reportError(event.reason, "UnhandledRejection"));
}
