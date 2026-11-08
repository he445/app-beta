// Clique simples × duplo clique na mesma miniatura (TAREFA 5): a ação do clique simples
// espera ~250 ms e é cancelada se vier o segundo clique, para não abrir as duas coisas.

export interface Timers {
  set(fn: () => void, ms: number): unknown;
  clear(handle: unknown): void;
}

const browserTimers: Timers = {
  set: (fn, ms) => setTimeout(fn, ms),
  clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

export const DOUBLE_CLICK_DELAY = 250;

export interface ClickController<T> {
  click(arg: T): void;
  doubleClick(arg: T): void;
  cancel(): void;
}

export function createClickController<T>(
  onSingle: (arg: T) => void,
  onDouble: (arg: T) => void,
  delay = DOUBLE_CLICK_DELAY,
  timers: Timers = browserTimers,
): ClickController<T> {
  let pending: unknown = null;
  const cancel = () => {
    if (pending !== null) timers.clear(pending);
    pending = null;
  };
  return {
    click(arg) {
      cancel();
      pending = timers.set(() => {
        pending = null;
        onSingle(arg);
      }, delay);
    },
    doubleClick(arg) {
      cancel();
      onDouble(arg);
    },
    cancel,
  };
}
