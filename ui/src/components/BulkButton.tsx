// "Corrigir pasta" e "Corrigir tudo" (ADR-0024): o mesmo caso de uso, com escopo da pasta
// ou da caixa. Com a caixa em análise, valem para as pastas já prontas.
import { useState } from "react";
import { useBulkOperations, useStartBulk, useUndoBulk, type BulkStart } from "../api/hooks";
import type { BulkCorrection, QaDocument } from "../api/types";
import { activeOperation, isActive, operationSummary, progressView } from "../lib/corrections";
import { navigate } from "../router";

/** Progresso de uma operação em andamento e, quando termina, o resumo com "Desfazer". */
export function OperationStatus({
  batchId,
  op,
  documentName,
}: {
  batchId: string;
  op: BulkCorrection | undefined;
  documentName?: string;
}) {
  const undo = useUndoBulk(batchId);
  if (!op) return null;
  if (isActive(op)) {
    const view = progressView(op);
    return (
      <div className="op-status" role="status" aria-live="polite">
        <div className="progress small"><div style={{ width: `${view.percent}%` }} /></div>
        <span className="small muted">{view.title} {view.detail}</span>
      </div>
    );
  }
  const canUndo = op.status === "applied" && (op.result?.applied_total ?? 0) > 0;
  return (
    <div className="op-status" role="status" aria-live="polite">
      <span className="small">{operationSummary(op, documentName)}</span>
      {canUndo && (
        <button className="link small" disabled={undo.isPending} onClick={() => undo.mutate(op.id)}>
          Desfazer
        </button>
      )}
      {undo.error && <span className="small error-inline">{undo.error.message}</span>}
    </div>
  );
}

/** Dispara uma operação em lote e acompanha só a que este componente iniciou. */
export function useOwnBulk(batchId: string) {
  const ops = useBulkOperations(batchId);
  const start = useStartBulk(batchId);
  const [mine, setMine] = useState<string>();
  const busy = Boolean(activeOperation(ops.data)) || start.isPending;
  const run = (req: BulkStart, onStarted?: (op: BulkCorrection) => void) =>
    start.mutate(req, {
      onSuccess: (op) => {
        setMine(op.id);
        onStarted?.(op);
      },
    });
  return { busy, run, error: start.error, op: ops.data?.find((o) => o.id === mine) };
}

export function BulkButtons({
  batchId,
  document,
  analyzing = false,
  openSequence = false,
  className = "",
}: {
  batchId: string;
  /** Pasta em foco: mostra "Corrigir pasta". */
  document?: Pick<QaDocument, "id" | "name">;
  /** Caixa ainda em análise: "Corrigir tudo" vale para as pastas prontas. */
  analyzing?: boolean;
  /** Depois de "Corrigir tudo" com a caixa analisada, abre a Sequência (painel do lote). */
  openSequence?: boolean;
  className?: string;
}) {
  const bulk = useOwnBulk(batchId);
  return (
    <div className={`bulk-buttons ${className}`}>
      <div className="row tight wrap">
        {document && (
          <button
            disabled={bulk.busy}
            title={`Aplica as correções automáticas pendentes só da pasta ${document.name}`}
            onClick={() => bulk.run({ documentId: document.id })}
          >
            Corrigir pasta
          </button>
        )}
        <button
          disabled={bulk.busy}
          title={
            analyzing
              ? "A caixa ainda está em análise: corrige as pastas já prontas. Rode de novo quando a análise terminar."
              : "Aplica as correções automáticas pendentes de todas as pastas da caixa"
          }
          onClick={() =>
            bulk.run({}, () => {
              if (openSequence && !analyzing) navigate({ name: "sequence", id: batchId });
            })
          }
        >
          {analyzing ? "Corrigir tudo (pastas prontas)" : "Corrigir tudo"}
        </button>
      </div>
      <OperationStatus batchId={batchId} op={bulk.op} documentName={document?.name} />
      {bulk.error && <span className="small error-inline">{bulk.error.message}</span>}
    </div>
  );
}
