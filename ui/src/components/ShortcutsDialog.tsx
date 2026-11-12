// Tela de atalhos (tecla ?): os atalhos de cada tela num lugar só.
import { useEffect, useState } from "react";
import { SHORTCUT_GROUPS, isHelpKey, isTyping } from "../lib/keys";

export function ShortcutsDialog() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (open && e.key === "Escape") {
        setOpen(false);
        return;
      }
      if (isTyping(e.target) || !isHelpKey(e)) return;
      e.preventDefault();
      setOpen((v) => !v);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("qa:atalhos", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("qa:atalhos", onOpen);
    };
  }, [open]);
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={() => setOpen(false)}>
      <div className="modal card shortcuts" role="dialog" aria-label="Atalhos de teclado" onClick={(e) => e.stopPropagation()}>
        <div className="row">
          <h2>Atalhos de teclado</h2>
          <button className="link" onClick={() => setOpen(false)} aria-label="Fechar">Fechar (Esc)</button>
        </div>
        <div className="shortcut-groups">
          {SHORTCUT_GROUPS.map((group) => (
            <section key={group.title}>
              <h3>{group.title}</h3>
              <dl>
                {group.keys.map(([k, v]) => (
                  <div key={k}>
                    <dt><kbd>{k}</kbd></dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
        <p className="small muted">O manual do conferente explica o passo a passo de uma caixa.</p>
      </div>
    </div>
  );
}
