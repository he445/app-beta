// Espera o motor acordar (plano gratuito do Render: até ~1 minuto depois de dormir).

export interface WakeOptions {
  timeoutMs?: number;
  /** Intervalos entre tentativas, em ms; o último se repete. */
  delaysMs?: number[];
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  onAttempt?: (attempt: number, elapsedMs: number, error: unknown) => void;
  signal?: AbortSignal;
}

const realSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Chama ``check`` até dar certo ou até ``timeoutMs``. Devolve o resultado da primeira
 * tentativa bem-sucedida; esgotado o prazo, relança o último erro.
 */
export async function waitForEngine<T>(check: () => Promise<T>, options: WakeOptions = {}): Promise<T> {
  const {
    timeoutMs = 90_000,
    delaysMs = [500, 1000, 2000, 3000, 5000],
    sleep = realSleep,
    now = () => Date.now(),
    onAttempt,
    signal,
  } = options;
  const start = now();
  let attempt = 0;
  for (;;) {
    attempt += 1;
    try {
      return await check();
    } catch (err) {
      const elapsed = now() - start;
      onAttempt?.(attempt, elapsed, err);
      if (signal?.aborted || elapsed >= timeoutMs) throw err;
      const delay = delaysMs[Math.min(attempt - 1, delaysMs.length - 1)] ?? 1000;
      await sleep(Math.min(delay, Math.max(0, timeoutMs - elapsed)));
    }
  }
}
