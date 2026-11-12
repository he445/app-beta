// Token de administrador: só na memória desta aba, nunca no armazenamento do navegador.
// Usado no Diagnóstico e para destravar os ajustes das digitalizadoras e dos perfis.
let token = "";
const listeners = new Set<() => void>();

export function adminToken(): string {
  return token;
}

export function setAdminToken(value: string): void {
  token = value.trim();
  listeners.forEach((fn) => fn());
}

export function onAdminTokenChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
