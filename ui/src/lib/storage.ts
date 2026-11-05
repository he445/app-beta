// Conveniências por navegador. O armazenamento pode falhar (aba privada): nunca é essencial.
export function readStore(key: string, fallback = ""): string {
  try {
    return window.sessionStorage.getItem(key) ?? window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

export function writeStore(key: string, value: string, session = false): void {
  try {
    (session ? window.sessionStorage : window.localStorage).setItem(key, value);
  } catch {
    /* sem armazenamento: segue só em memória */
  }
}

export function clearStore(key: string): void {
  try {
    window.sessionStorage.removeItem(key);
    window.localStorage.removeItem(key);
  } catch {
    /* ignorado */
  }
}
