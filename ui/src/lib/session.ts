// Sessão aberta pelo próprio motor (capacidade ``os_session``): o token vem da janela do
// programa (ou de um código de uso único no fragmento da URL) e o revisor é o usuário do
// sistema. Sem essa capacidade, nada muda: a tela de entrada pede o nome (e o token).
import { api, getSession, json, setSession } from "../api/client";
import { hasCapability } from "../api/engine";
import type { Health, SessionInfo } from "../api/types";
import { desktopApi, takeFragmentCode } from "./desktop";

export async function adoptEngineSession(engine: Health): Promise<void> {
  if (!hasCapability(engine, "os_session")) return;
  const current = getSession();
  let token = current.token;
  if (engine.auth_required) {
    const { code, rest } = takeFragmentCode(window.location.hash);
    if (code) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${rest}`);
      token = (await json<{ token: string }>("/session/exchange", "POST", { code })).token;
    } else {
      const bridge = await desktopApi();
      if (bridge?.get_session) token = (await bridge.get_session()).token;
    }
  }
  setSession({ ...current, token });
  const info = await api<SessionInfo>("/session");
  setSession({ ...getSession(), reviewer: info.reviewer ?? current.reviewer });
}
