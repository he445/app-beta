// Tela 9: perfis do cliente (limiares e regras como configuração, validados pelo motor).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { json } from "../api/client";
import { keys, useProfiles } from "../api/hooks";
import type { Profile } from "../api/types";
import { ErrorBox, Loading } from "../components/ui";

export function Profiles() {
  const profiles = useProfiles();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const current = profiles.data?.find((p) => p.id === selected) ?? profiles.data?.[0];

  useEffect(() => {
    if (current) setText(JSON.stringify(current, null, 2));
  }, [current]);

  async function save() {
    setError(null);
    setSaved(false);
    try {
      const body = JSON.parse(text) as Profile;
      await json<Profile>(`/profiles/${body.id}`, "PUT", body);
      await qc.invalidateQueries({ queryKey: keys.profiles });
      setSelected(body.id);
      setSaved(true);
    } catch (err) {
      setError(err instanceof SyntaxError ? new Error(`JSON inválido: ${err.message}`) : err);
    }
  }

  if (profiles.isLoading) return <Loading />;
  return (
    <div className="split">
      <aside className="doc-list">
        {profiles.data?.map((p) => (
          <button key={p.id} className={`link-row ${p.id === current?.id ? "active" : ""}`} onClick={() => setSelected(p.id)}>
            {p.name}
          </button>
        ))}
      </aside>
      <main className="page">
        <h1>Perfil {current?.name}</h1>
        <p className="muted">
          Limiares, regras de numeração, tabela de estações e padrão de nomes. O motor valida contra
          <code> profile.schema.json</code> antes de salvar; para criar outro perfil, troque o <code>id</code>.
        </p>
        <textarea className="code" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label="Perfil em JSON" />
        <ErrorBox error={error} />
        {saved && <div className="ok-box">Perfil salvo.</div>}
        <button className="primary" onClick={() => void save()}>Salvar perfil</button>
      </main>
    </div>
  );
}
