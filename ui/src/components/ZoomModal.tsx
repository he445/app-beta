// Página ampliada num modal (TAREFA 5): zoom e arrasto do OpenSeadragon, alternância
// Original/Corrigida quando existe versão corrigida, setas e Esc.
import { useEffect, useRef, useState } from "react";
import { usePageImage } from "../api/hooks";
import { zoomModalKey } from "../lib/keys";
import { Viewer, type ViewerHandle } from "./Viewer";

export interface ZoomPage {
  pageId: string;
  label: string;
  hasCorrected: boolean;
}

interface Props {
  pages: ZoomPage[];
  index: number;
  preferCorrected: boolean;
  onClose: () => void;
}

export function ZoomModal({ pages, index: start, preferCorrected, onClose }: Props) {
  const [index, setIndex] = useState(start);
  const [showCorrected, setShowCorrected] = useState(preferCorrected);
  const viewer = useRef<ViewerHandle>(null);
  const page = pages[index];
  const corrected = Boolean(page?.hasCorrected) && showCorrected;
  const image = usePageImage(page?.pageId, corrected ? "corrected" : "original");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const action = zoomModalKey(e);
      if (!action) return;
      e.preventDefault();
      e.stopPropagation();
      if (action === "close") onClose();
      else if (action === "prev") setIndex((i) => Math.max(0, i - 1));
      else if (action === "next") setIndex((i) => Math.min(pages.length - 1, i + 1));
      else viewer.current?.toggleZoom();
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [pages.length, onClose]);

  if (!page) return null;
  return (
    <div className="modal-backdrop zoom-backdrop" onClick={onClose}>
      <div className="zoom-modal" role="dialog" aria-modal="true" aria-label={`Página ampliada: ${page.label}`} onClick={(e) => e.stopPropagation()}>
        <div className="zoom-head">
          <button onClick={() => setIndex((i) => Math.max(0, i - 1))} disabled={index === 0} aria-label="Página anterior">←</button>
          <strong>{page.label}</strong>
          <span className="muted small">{index + 1} de {pages.length}</span>
          <button onClick={() => setIndex((i) => Math.min(pages.length - 1, i + 1))} disabled={index === pages.length - 1} aria-label="Página seguinte">→</button>
          {page.hasCorrected && (
            <div className="before-after inline-toggle" role="group" aria-label="Versão">
              <button className={!showCorrected ? "active" : ""} onClick={() => setShowCorrected(false)}>Original</button>
              <button className={showCorrected ? "active" : ""} onClick={() => setShowCorrected(true)}>Corrigida</button>
            </div>
          )}
          <span className="muted small zoom-hint">Arraste para mover · roda do mouse ou espaço para ampliar · Esc fecha</span>
          <button className="link" onClick={onClose} aria-label="Fechar">Fechar</button>
        </div>
        <div className="zoom-body">
          <Viewer ref={viewer} url={image.data} />
          {!image.data && <div className="loading overlay-loading">Carregando a imagem…</div>}
        </div>
      </div>
    </div>
  );
}
