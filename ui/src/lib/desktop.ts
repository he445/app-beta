// Ponte com a janela do programa desktop (pywebview). Fora dela, tudo aqui devolve null:
// a interface decide o que mostrar pelas capacidades do motor, nunca por "se é desktop".

/** O que a janela expõe em ``window.pywebview.api`` (``entrypoints/desktop``). */
export interface DesktopApi {
  get_session(): Promise<{ token: string }>;
  pick_folder(): Promise<string | null>;
}

declare global {
  interface Window {
    pywebview?: { api?: Partial<DesktopApi> };
  }
}

const READY_EVENT = "pywebviewready";

/** A ponte da janela, se houver. A pywebview injeta a API pouco depois de carregar a página. */
export function desktopApi(timeoutMs = 3000): Promise<Partial<DesktopApi> | null> {
  if (typeof window === "undefined") return Promise.resolve(null);
  if (window.pywebview?.api) return Promise.resolve(window.pywebview.api);
  return new Promise((resolve) => {
    const done = () => {
      window.removeEventListener(READY_EVENT, done);
      clearTimeout(timer);
      resolve(window.pywebview?.api ?? null);
    };
    const timer = setTimeout(done, timeoutMs);
    window.addEventListener(READY_EVENT, done);
  });
}

/**
 * Código de uso único entregue no fragmento da URL (``#code=...``) quando o programa
 * abre no navegador padrão (sem WebView2). O fragmento não vai para o servidor nem
 * para o log. Devolve o código e o fragmento sem ele.
 */
export function takeFragmentCode(hash: string): { code: string | null; rest: string } {
  const match = /(?:^#|&)code=([A-Za-z0-9_-]+)/.exec(hash);
  if (!match) return { code: null, rest: hash };
  const rest = hash.replace(match[0], match[0].startsWith("&") ? "" : "#").replace(/^#&/, "#");
  return { code: match[1] ?? null, rest: rest === "#" ? "" : rest };
}

/** Escolhe uma pasta pelo diálogo nativo da janela; null se não houver ponte ou se cancelar. */
export async function pickFolder(): Promise<string | null> {
  const api = await desktopApi(0);
  return api?.pick_folder ? api.pick_folder() : null;
}
