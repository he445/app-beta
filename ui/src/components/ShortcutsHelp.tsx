// Tela de atalhos: tecla ? em qualquer tela, ou o botão "Atalhos" no topo.
import { useEffect, useRef } from "react";
import { SHORTCUT_GROUPS, type ShortcutGroup } from "../lib/keys";

export function ShortcutsHelp({ first, onClose }: { first?: ShortcutGroup["id"]; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => close.current?.focus(), []);
  // A tela atual primeiro; "Em qualquer tela" sempre no fim.
  const groups = [...SHORTCUT_GROUPS].sort((a, b) => rank(a.id, first) - rank(b.id, first));
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal card shortcuts-help"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape" || e.key === "?") {
            e.preventDefault();
            onClose();
          }
        }}
      >
        <div className="row">
          <h2 id="shortcuts-title" className="inline">Atalhos de teclado</h2>
          <button ref={close} className="link" onClick={onClose}>Fechar (Esc)</button>
        </div>
        {groups.map((g) => (
          <section key={g.id}>
            <h3>{g.title}</h3>
            <dl className="shortcut-list">
              {g.items.map(([k, v]) => (
                <div key={`${g.id}-${k}`}>
                  <dt><kbd>{k}</kbd></dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
        <p className="small muted">O passo a passo completo está no manual do conferente (docs/operacao).</p>
      </div>
    </div>
  );
}

function rank(id: ShortcutGroup["id"], first?: ShortcutGroup["id"]): number {
  if (id === first) return 0;
  return id === "global" ? 9 : 1;
}
