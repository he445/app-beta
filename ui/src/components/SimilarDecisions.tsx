// "Decidir semelhantes" (ADR-0024): a mesma decisão em todas as sinalizações pendentes da
// categoria (regra) da que está na tela, na pasta ou na caixa. Dá para desfazer em lote.
import { useState } from "react";
import type { Analysis, BulkDecision, QaDocument } from "../api/types";
import { BULK_DECISION_LABEL, NO_SIMILAR_RULES, similarCounts } from "../lib/corrections";
import { ruleLabel } from "../lib/format";
import { OperationStatus, useOwnBulk } from "./BulkButton";

export function SimilarDecisions({
  batchId,
  report,
  rule,
  document,
}: {
  batchId: string;
  report: Analysis;
  rule: string;
  document: QaDocument | undefined;
}) {
  const [action, setAction] = useState<BulkDecision>("approve");
  const bulk = useOwnBulk(batchId);
  const label = ruleLabel(rule);

  if (NO_SIMILAR_RULES.has(rule)) {
    return (
      <div className="similar">
        <h3>Decidir semelhantes</h3>
        <p className="small muted">{label}: decida uma por uma. Não entra em decisão em lote.</p>
      </div>
    );
  }

  const counts = similarCounts(report, rule, document);
  function run(where: "folder" | "box") {
    const n = where === "folder" ? counts.folder : counts.box;
    const place = where === "folder" ? `da pasta ${document?.name ?? ""}` : "da caixa inteira";
    const ok = window.confirm(
      `${BULK_DECISION_LABEL[action]}: aplicar em ${n} sinalização(ões) pendente(s) de "${label}" ${place}?\n\nDá para desfazer em lote depois.`,
    );
    if (!ok) return;
    bulk.run({ rule, action, documentId: where === "folder" ? document?.id : undefined });
  }

  return (
    <div className="similar">
      <h3>Decidir semelhantes: {label}</h3>
      <select
        aria-label="Decisão para todas as semelhantes"
        value={action}
        onChange={(e) => setAction(e.target.value as BulkDecision)}
      >
        {(Object.keys(BULK_DECISION_LABEL) as BulkDecision[]).map((a) => (
          <option key={a} value={a}>{BULK_DECISION_LABEL[a]}</option>
        ))}
      </select>
      <div className="row tight wrap">
        {document && (
          <button disabled={bulk.busy || counts.folder === 0} onClick={() => run("folder")}>
            Nesta pasta ({counts.folder})
          </button>
        )}
        <button disabled={bulk.busy || counts.box === 0} onClick={() => run("box")}>
          Na caixa ({counts.box})
        </button>
      </div>
      <OperationStatus batchId={batchId} op={bulk.op} documentName={document?.name} />
      {bulk.error && <span className="small error-inline">{bulk.error.message}</span>}
    </div>
  );
}
