// Cliente HTTP fino: autenticação Bearer, erros RFC 9457 e download de binários.
import { clearStore, readStore, writeStore } from "../lib/storage";

const BASE_KEY = "qa.apiBase";
const TOKEN_KEY = "qa.token";
const REVIEWER_KEY = "qa.reviewer";

export interface Session {
  base: string;
  token: string;
  reviewer: string;
}

let session: Session = {
  base: readStore(BASE_KEY, import.meta.env.VITE_API_URL ?? "/api"),
  token: readStore(TOKEN_KEY),
  reviewer: readStore(REVIEWER_KEY),
};
const listeners = new Set<() => void>();

export function getSession(): Session {
  return session;
}

export function setSession(next: Session): void {
  session = next;
  writeStore(BASE_KEY, next.base);
  writeStore(REVIEWER_KEY, next.reviewer);
  writeStore(TOKEN_KEY, next.token, true); // token só na sessão da aba
  listeners.forEach((l) => l());
}

export function logout(): void {
  clearStore(TOKEN_KEY);
  session = { ...session, token: "" };
  listeners.forEach((l) => l());
}

export function onSessionChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly title: string,
    readonly detail?: string,
  ) {
    super(detail ? `${title}: ${detail}` : title);
  }
}

function headers(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  if (session.token) h.set("Authorization", `Bearer ${session.token}`);
  return h;
}

export async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${session.base}${path}`, { ...init, headers: headers(init.headers) });
  if (!response.ok) {
    let title = response.statusText || `Erro ${response.status}`;
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { title?: string; detail?: string };
      title = body.title ?? title;
      detail = body.detail;
    } catch {
      /* corpo não é JSON */
    }
    if (response.status === 401) logout();
    throw new ApiError(response.status, title, detail);
  }
  return response;
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
