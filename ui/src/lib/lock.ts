// Trava por caixa: quem está conferindo, e se a trava foi abandonada.
import { ApiError } from "../api/client";

export interface LockConflict {
  detail: string;
  stale: boolean;
}

/** A caixa está em conferência em outra máquina? (409 com a trava). */
export function lockConflict(error: unknown): LockConflict | null {
  if (!(error instanceof ApiError) || error.status !== 409 || !("lock" in error.body)) return null;
  return { detail: error.detail ?? error.title, stale: Boolean(error.body.stale) };
}

export const RENEW_MS = 60_000;
