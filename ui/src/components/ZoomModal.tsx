// Página ampliada num modal (TAREFA 5): zoom e arrasto do OpenSeadragon, alternância
// Original/Corrigida quando existe versão corrigida, setas e Esc. Na sequência, também
// decide a página sem fechar o zoom: Aprovar (A) ou Defeito de origem com ressalva (O).
import { useEffect, useRef, useState } from "react";
import { usePageImage } from "../api/hooks";
import { isTyping, zoomModalKey } from "../lib/keys";
import { Viewer, type ViewerHandle } from "./Viewer";

export interface ZoomPage {
  pageId: string;
  label: string;
  hasCorrected: boolean;
}

export type ZoomDecision = "approve" | "source_defect";

/** Decisão rápida: quantas sinalizações a página ainda tem e como decidi-las. */
export interface ZoomDecisions {
  pending: (pageId: string) => number;
  decide: (pageId: string, action: ZoomDecision, note?: string) => Promise<number>;
}

interface Props {
  pages: ZoomPage[];
  index: number;
  preferCorrected: boolean;
  onClose: () => void;
  decisions?: ZoomDecisions;
}

const DONE: Record<ZoomDecision, string> = {
  approve: "aprovada(s)",
  source_defect: "como defeito de origem",
};

export function ZoomModal({ pages, index: start, preferCorrected, onClose, decisions }: Props) {
  const [index, setIndex] = useState(start);
  const [showCorrected, setShowCorrected] = useState(preferCorrected);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; tone: "ok" | "bad" } | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const noteInput = useRef<HTMLInputElement>(null);
  const viewer = useRef<ViewerHandle>(null);
  const page = pages[index];
  const corrected = Boolean(page?.hasCorrected) && showCorrected;
  const image = usePageImage(page?.pageId, corrected ? "corrected" : "original");
  const pending = page && decisions ? decisions.pending(page.pageId) : 0;

  useEffect(() => {
    if (noteOpen) noteInput.current?.focus();
  }, [noteOpen]);

  // Decide as sinalizações pendentes da página e passa para a seguinte (como na revisão).
  async function decide(action: ZoomDecision, withNote?: string) {
    if (!decisions || !page || busy) return;
    if (pending === 0) {
      setNotice({ text: "Esta página não tem sinalização pendente.", tone: "ok" });
      return;
    }
    setBusy(true);
    try {
      const n = await decisions.decide(page.pageId, action, withNote);
      const ressalva = withNote?.trim() ? ` Ressalva: “${withNote.trim()}”.` : "";
      setNotice({ text: `${page.label}: ${n} sinalização(ões) ${DONE[action]}.${ressalva}`, tone: "ok" });
      setNoteOpen(false);
      setNote("");
      setIndex((i) => Math.min(pages.length - 1, i + 1));
    } catch (err) {
      setNotice({ text: err instanceof Error ? err.message : String(err), tone: "bad" });
    } finally {
      setBusy(false);
    }
  }
  const decideRef = useRef(decide);
  decideRef.current = decide;

  function openNote() {
    if (pending === 0) {
      setNotice({ text: "Esta página não tem sinalização pendente.", tone: "ok" });
      return;
    }
    setNoteOpen(true);
  }
  const openNoteRef = useRef(openNote);
  openNoteRef.current = openNote;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isTyping(e.target)) return; // o campo da ressalva cuida de Enter e Esc
      const action = zoomModalKey(e);
      if (!action) return;
      if ((action === "approve" || action === "source_defect") && !decisions) return;
      e.preventDefault();
      e.stopPropagation();
      if (action === "close") onClose();
      else if (action === "prev") setIndex((i) => Math.max(0, i - 1));
      else if (action === "next") setIndex((i) => Math.min(pages.length - 1, i + 1));
      else if (action === "approve") void decideRef.current("approve");
      else if (action === "source_defect") openNoteRef.current();
      else viewer.current?.toggleZoom();
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [pages.length, onClose, decisions]);

  // Ao trocar de página, a ressalva começa vazia.
  useEffect(() => {
    setNoteOpen(false);
    setNote("");
  }, [index]);

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
          {decisions && (
            <>
              <button
                className="primary zoom-approve"
                disabled={busy || pending === 0}
                onClick={() => void decide("approve")}
                title="Aprova (falso positivo) as sinalizações pendentes desta página e passa para a seguinte"
              >
                <kbd>A</kbd> {busy ? "Gravando…" : pending > 0 ? `Aprovar (${pending})` : "Sem pendência"}
              </button>
              <button
                className="zoom-approve"
                disabled={busy || pending === 0}
                onClick={openNote}
                title="O problema veio do papel: aceita a página como está, com ressalva, e passa para a seguinte"
              >
                <kbd>O</kbd> Defeito de origem
              </button>
            </>
          )}
          <span className="muted small zoom-hint">Arraste para mover · roda do mouse ou espaço para ampliar · Esc fecha</span>
          <button className="link" onClick={onClose} aria-label="Fechar">Fechar</button>
        </div>
        {noteOpen && (
          <form
            className="zoom-note"
            onSubmit={(e) => {
              e.preventDefault();
              void decide("source_defect", note);
            }}
          >
            <label className="small" htmlFor="zoom-note-input">Ressalva (opcional, vai para o relatório):</label>
            <input
              id="zoom-note-input"
              ref={noteInput}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ex.: original manchado; folha rasgada no papel"
              autoComplete="off"
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.preventDefault();
                  e.stopPropagation();
                  setNoteOpen(false);
                }
              }}
            />
            <button className="primary" disabled={busy}>Confirmar defeito de origem ({pending})</button>
            <button type="button" className="link" onClick={() => setNoteOpen(false)}>Cancelar</button>
          </form>
        )}
        {notice && (
          <div className={`zoom-notice small ${notice.tone === "bad" ? "error-inline" : ""}`} role="status">
            {notice.text}
          </div>
        )}
        <div className="zoom-body">
          <Viewer ref={viewer} url={image.data} />
          {!image.data && <div className="loading overlay-loading">Carregando a imagem…</div>}
        </div>
      </div>
    </div>
  );
}
