// "Corrigir o lote inteiro": mesmo caso de uso do "Corrigir tudo", com escopo de lote.
import { useBulkOperations, useStartBulk } from "../api/hooks";
import { activeOperation } from "../lib/corrections";
import { navigate } from "../router";

export function BulkBatchButton({ batchId, className = "" }: { batchId: string; className?: string }) {
  const ops = useBulkOperations(batchId);
  const start = useStartBulk(batchId);
  const busy = Boolean(activeOperation(ops.data)) || start.isPending;
  return (
    <>
      <button
        className={className}
        disabled={busy}
        title="Aplica as correções automáticas pendentes de todos os documentos e mostra o resultado na sequência"
        onClick={() =>
          start.mutate(undefined, { onSuccess: () => navigate({ name: "sequence", id: batchId }) })
        }
      >
        {busy ? "Corrigindo…" : "Corrigir o lote inteiro"}
      </button>
      {start.error && <span className="small error-inline">{start.error.message}</span>}
    </>
  );
}
