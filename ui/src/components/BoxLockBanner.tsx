// Trava por caixa enquanto o lote está aberto: renova a cada minuto e avisa se a caixa
// está em conferência em outra máquina ou se a trava vale só neste computador.
import { useMutation } from "@tanstack/react-query";
import { useEffect } from "react";
import { json } from "../api/client";
import { RENEW_MS, lockConflict } from "../lib/lock";

interface LockState {
  shared: boolean;
  boxes: { box: string }[];
}

export function BoxLockBanner({ batchId }: { batchId: string }) {
  const lock = useMutation({
    mutationFn: (takeOver: boolean) => json<LockState>(`/batches/${batchId}/lock`, "POST", takeOver ? { take_over: true } : {}),
  });
  const { mutate } = lock;
  useEffect(() => {
    mutate(false);
    const timer = setInterval(() => mutate(false), RENEW_MS);
    return () => clearInterval(timer);
  }, [batchId, mutate]);

  const conflict = lockConflict(lock.error);
  if (conflict) {
    return (
      <div className="lock-banner warning" role="alert">
        {conflict.detail} Suas mudanças podem conflitar com as de quem está com a caixa.
        {conflict.stale && (
          <button className="small-btn" onClick={() => lock.mutate(true)} disabled={lock.isPending}>
            Assumir a caixa
          </button>
        )}
      </div>
    );
  }
  if (lock.data && !lock.data.shared) {
    return (
      <div className="lock-banner small muted" role="status">
        Trava da caixa só neste computador: sem a pasta compartilhada de relatórios, outra máquina não vê que esta caixa
        está em conferência.
      </div>
    );
  }
  return null;
}
