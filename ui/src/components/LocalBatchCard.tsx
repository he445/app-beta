// Abrir um lote numa pasta do computador ou da rede, lido no lugar (capacidade local_batches).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { json } from "../api/client";
import { keys, useProfiles } from "../api/hooks";
import type { BatchStatus } from "../api/types";
import { boxLockedFrom } from "../lib/boxLocks";
import { desktopApi, pickFolder } from "../lib/desktop";
import { navigate } from "../router";
import { Card, ErrorBox, Loading } from "./ui";

export function LocalBatchCard() {
  const profiles = useProfiles();
  const qc = useQueryClient();
  const [path, setPath] = useState("");
  const [profileId, setProfileId] = useState("");
  const [station, setStation] = useState("");
  const [nativePicker, setNativePicker] = useState(false);

  useEffect(() => {
    let alive = true;
    void desktopApi().then((api) => alive && setNativePicker(Boolean(api?.pick_folder)));
    return () => {
      alive = false;
    };
  }, []);

  const list = profiles.data ?? [];
  const chosen = profileId || (list.some((p) => p.id === "sos-piloto") ? "sos-piloto" : (list[0]?.id ?? ""));
  const stations = (list.find((p) => p.id === chosen)?.stations ?? []).filter((s) => s.id);

  const open = useMutation({
    mutationFn: (takeOver: boolean) =>
      json<BatchStatus>("/local-batches", "POST", {
        path: path.trim(),
        profile_id: chosen,
        ...(station ? { station_id: station } : {}),
        ...(takeOver ? { take_over: true } : {}),
      }),
    onSuccess: (status) => {
      void qc.invalidateQueries({ queryKey: keys.batches });
      navigate({ name: "batch", id: status.id });
    },
  });

  const locked = boxLockedFrom(open.error);

  return (
    <Card title="Abrir lote">
      <p className="small muted">
        A pasta é lida no lugar, só para leitura: nada é copiado nem alterado. O lote corrigido vai
        para a pasta de saída.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (path.trim()) open.mutate(false);
        }}
      >
        <label>
          Pasta do lote
          <div className="row tight">
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder={"D:\\Lotes\\0412 ou \\\\servidor\\digitalizacao\\0412"}
              aria-label="Pasta do lote"
              spellCheck={false}
            />
            {nativePicker && (
              <button
                type="button"
                onClick={() => void pickFolder().then((picked) => picked && setPath(picked))}
              >
                Escolher pasta…
              </button>
            )}
          </div>
        </label>
        <label>
          Perfil
          {profiles.isLoading ? (
            <Loading />
          ) : (
            <select value={chosen} onChange={(e) => setProfileId(e.target.value)}>
              {list.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
        </label>
        {stations.length > 0 && (
          <label>
            Estação (quando o arquivo não diz de qual digitalizadora veio)
            <select value={station} onChange={(e) => setStation(e.target.value)}>
              <option value="">Estação padrão deste computador</option>
              {stations.map((s) => (
                <option key={s.id} value={s.id}>{s.location}</option>
              ))}
            </select>
          </label>
        )}
        {locked ? (
          <div className="warning" role="alert">
            <ul className="plain">
              {locked.locks.map((lock) => (
                <li key={lock.box}>{lock.message}</li>
              ))}
            </ul>
            {locked.can_take_over ? (
              <>
                <p className="small">Assumir fica registrado com o seu nome, na trava e no histórico da pasta compartilhada.</p>
                <button type="button" onClick={() => open.mutate(true)} disabled={open.isPending}>
                  Assumir a caixa
                </button>
              </>
            ) : (
              <p className="small">Escolha outra caixa ou espere a conferência terminar.</p>
            )}
          </div>
        ) : (
          <ErrorBox error={open.error} />
        )}
        <button className="primary" disabled={!path.trim() || open.isPending}>
          {open.isPending ? "Abrindo…" : "Analisar lote"}
        </button>
      </form>
    </Card>
  );
}
