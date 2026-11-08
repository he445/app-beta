// Tela de carregamento do "Corrigir tudo": progresso real vindo do motor.
import type { BulkCorrection } from "../api/types";
import { progressView } from "../lib/corrections";

export function CorrectionProgress({ op }: { op: BulkCorrection | undefined }) {
  const view = progressView(op);
  return (
    <div className="progress-overlay" role="status" aria-live="polite">
      <div className="card progress-card">
        <h2>{view.title}</h2>
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={view.percent}>
          <div style={{ width: `${view.percent}%` }} />
        </div>
        <p className="muted small">{view.detail || " "}</p>
        <p className="small muted">
          Só correções automáticas: endireitar, recortar bordas, ajustar brilho, remover página em
          branco e reordenar pela numeração. O original não é alterado.
        </p>
      </div>
    </div>
  );
}
