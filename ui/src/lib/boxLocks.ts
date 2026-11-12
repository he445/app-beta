// Trava por caixa: o que dizer quando a caixa está noutra máquina e no painel do lote.
import { ApiError } from "../api/client";
import type { BoxLocked, BoxLocks } from "../api/types";

/** O 409 de abrir lote com caixa travada, ou null para qualquer outro erro. */
export function boxLockedFrom(error: unknown): BoxLocked | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const locks = error.body.locks;
  if (!Array.isArray(locks) || locks.length === 0) return null;
  return error.body as unknown as BoxLocked;
}

export interface LockNotice {
  tone: "warn" | "bad";
  text: string;
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/** Avisos do painel: caixa assumida por outra máquina e trava que vale só aqui. */
export function lockNotices(view: BoxLocks | undefined): LockNotice[] {
  if (!view?.enabled) return [];
  const notices: LockNotice[] = [];
  for (const box of view.boxes) {
    if (box.state !== "lost") continue;
    const who = box.holder ? `${box.holder.reviewer}, na máquina ${box.holder.machine}` : "outra máquina";
    const since = box.ended_at ? ` (percebido em ${when(box.ended_at)})` : "";
    notices.push({
      tone: "bad",
      text:
        `A caixa ${box.box} foi assumida por ${who}${since}. O que você já decidiu continua neste ` +
        "computador, mas a conferência dela agora é feita lá.",
    });
  }
  const held = view.boxes.filter((b) => b.state === "held");
  const local = held.filter((b) => b.scope === "local");
  if (local.length > 0) {
    notices.push({
      tone: "warn",
      text: view.shared_configured
        ? "A pasta compartilhada de relatórios está fora do ar: a trava da caixa vale só neste computador até ela voltar."
        : "A trava da caixa vale só neste computador: sem a pasta compartilhada de relatórios (reports_dir), outra máquina pode abrir a mesma caixa.",
    });
  }
  return notices;
}
