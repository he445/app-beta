// Cliente HTTP fino: base do motor, autenticação Bearer opcional, erros RFC 9457 e de rede.
import { clearStore, readStore, writeStore } from "../lib/storage";
import type { Health } from "./types";

export type { Health } from "./types";

// Chaves novas: a versão anterior gravava o endereço do motor e o reusava para sempre,
// por cima do endereço da publicação; um endereço velho no celular dava "Failed to fetch".
const BASE_OVERRIDE_KEY = "qa.apiBaseOverride";
const TOKEN_KEY = "qa.token";
const REVIEWER_KEY = "qa.reviewer";

/** Endereço do motor da publicação: "" = mesma origem; "/api" = proxy do Vite. */
export const DEFAULT_BASE = normalizeBase(import.meta.env.VITE_API_URL ?? "/api");

/**
 * Normaliza o endereço do motor: sem barra no fim (evita "//batches") e com
 * https:// quando vier só o nome do servidor (ex.: "qa-motor.onrender.com").
 */
export function normalizeBase(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed || trimmed.startsWith("/") || /^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

export interface Session {
  base: string;
  token: string;
  reviewer: string;
}

let session: Session = {
  base: normalizeBase(readStore(BASE_OVERRIDE_KEY, DEFAULT_BASE)),
  token: readStore(TOKEN_KEY),
  reviewer: readStore(REVIEWER_KEY),
};
const listeners = new Set<() => void>();

export function getSession(): Session {
  return session;
}

export function setSession(next: Session): void {
  session = { ...next, base: normalizeBase(next.base) };
  if (session.base === DEFAULT_BASE) clearStore(BASE_OVERRIDE_KEY);
  else writeStore(BASE_OVERRIDE_KEY, session.base);
  writeStore(REVIEWER_KEY, session.reviewer);
  if (session.token) writeStore(TOKEN_KEY, session.token, true); // token só na sessão da aba
  else clearStore(TOKEN_KEY);
  listeners.forEach((l) => l());
}

/** Sai: esquece o token; no modo só com nome, esquece o nome (troca de revisor). */
export function logout(): void {
  clearStore(TOKEN_KEY);
  if (!session.token) clearStore(REVIEWER_KEY);
  session = { ...session, token: "", reviewer: session.token ? session.reviewer : "" };
  listeners.forEach((l) => l());
}

export function onSessionChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Valor recusado pelo motor, um por chave (configuração inválida). */
export interface FieldProblem {
  key: string;
  source: string;
  expected: string;
  value?: unknown;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly title: string,
    readonly detail?: string,
    readonly problems: FieldProblem[] = [],
  ) {
    super(detail ? `${title}: ${detail}` : title);
  }
}

/** Status das falhas de rede (sem resposta HTTP). */
export const NETWORK_ERROR = 0;

/**
 * Traduz a falha de rede do navegador ("Failed to fetch", "Load failed",
 * "NetworkError...") numa mensagem que diz o que fazer.
 */
export function networkError(base: string): ApiError {
  const where = base || (typeof window === "undefined" ? "mesma origem" : window.location.origin);
  return new ApiError(
    NETWORK_ERROR,
    "Sem conexão com o motor de análise",
    `Endereço: ${where}. Verifique a internet do aparelho; se o motor estiver no plano ` +
      "gratuito do Render, ele leva até 1 minuto para acordar: tente de novo.",
  );
}

function headers(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  if (session.token) h.set("Authorization", `Bearer ${session.token}`);
  return h;
}

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${session.base}${path}`, { ...init, headers: headers(init.headers) });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw networkError(session.base);
  }
}

export async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await send(path, init);
  if (!response.ok) {
    let title = response.statusText || `Erro ${response.status}`;
    let detail: string | undefined;
    let problems: FieldProblem[] = [];
    try {
      const body = (await response.json()) as { title?: string; detail?: string; problems?: FieldProblem[] };
      title = body.title ?? title;
      detail = body.detail;
      problems = body.problems ?? [];
    } catch {
      /* corpo não é JSON (ex.: página do Render enquanto o motor acorda) */
    }
    if (response.status === 401) {
      if (session.token) logout();
      else detail = "O motor exige token de acesso: recarregue a página para informá-lo.";
    }
    if (response.status === 502 || response.status === 503) {
      detail = detail ?? "O motor está reiniciando ou acordando. Tente de novo em alguns segundos.";
    }
    throw new ApiError(response.status, title, detail, problems);
  }
  return response;
}

/** ``GET /health`` (público): o motor está no ar e o que a entrada deve pedir. */
export async function health(base = session.base): Promise<Health> {
  let response: Response;
  try {
    response = await fetch(`${normalizeBase(base)}/health`, { cache: "no-store" });
  } catch {
    throw networkError(normalizeBase(base));
  }
  if (!response.ok) throw new ApiError(response.status, `O motor respondeu ${response.status}`);
  return (await response.json()) as Health;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await raw(path, init);
  return (await response.json()) as T;
}

export function json<T>(path: string, method: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

export async function blobUrl(path: string): Promise<string> {
  const response = await raw(path);
  return URL.createObjectURL(await response.blob());
}

export async function download(path: string, filename: string): Promise<void> {
  const url = await blobUrl(path);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
