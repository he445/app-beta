// Tela 1: enviar lote. Também lista os lotes recentes.
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { raw } from "../api/client";
import { keys, useBatches, useProfiles } from "../api/hooks";
import type { BatchStatus } from "../api/types";
import { Card, ErrorBox, Loading } from "../components/ui";
import { filesFromDrop, filesFromInput, type PickedFile } from "../lib/files";
import { VERDICT_LABEL } from "../lib/format";
import { href, navigate } from "../router";

export function Home() {
  const profiles = useProfiles();
  const batches = useBatches();
  const qc = useQueryClient();
  const [files, setFiles] = useState<PickedFile[]>([]);
  const [profile, setProfile] = useState("demo");
  const [name, setName] = useState("");
  const [manifest, setManifest] = useState<File | null>(null);
  const [numbering, setNumbering] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const zipInput = useRef<HTMLInputElement>(null);

  async function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const picked = await filesFromDrop(e.dataTransfer.items);
    adopt(picked);
  }

  function adopt(picked: PickedFile[]) {
    // numbering.json e manifest.csv soltos na pasta vão nos campos próprios.
    const sidecarNumbering = picked.find((p) => p.path.endsWith("numbering.json"));
    if (sidecarNumbering) setNumbering(sidecarNumbering.file);
    setFiles(picked);
    const root = picked[0]?.path.split("/")[0];
    if (!name && root && picked.length > 1) setName(root);
  }

  async function send() {
    setSending(true);
    setError(null);
    try {
      const form = new FormData();
      for (const f of files) form.append("files", f.file, f.path);
      form.append("profile_id", profile);
      if (name) form.append("name", name);
      if (manifest) form.append("manifest", manifest);
      if (numbering) form.append("numbering", numbering);
      const res = await raw("/batches", { method: "POST", body: form });
      const status = (await res.json()) as BatchStatus;
      void qc.invalidateQueries({ queryKey: keys.batches });
      navigate({ name: "batch", id: status.id });
    } catch (err) {
      setError(err);
    } finally {
      setSending(false);
    }
  }

  const size = files.reduce((n, f) => n + f.file.size, 0);

  return (
    <div className="page">
      <h1>Enviar lote</h1>
      <div className="warning" role="note">
        <strong>Somente documentos sintéticos ou públicos.</strong> Documento de cliente é proibido neste
        servidor de demonstração. Os lotes são apagados automaticamente após 24 horas.
      </div>
      <div className="grid-2">
        <Card>
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            {files.length ? (
              <>
                <strong>{files.length} arquivo(s)</strong>
                <span className="muted">{(size / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB</span>
                <button className="link" onClick={() => setFiles([])}>Limpar</button>
              </>
            ) : (
              <>
                <strong>Arraste a pasta do lote ou um .zip</strong>
                <span className="muted">TIFF, JPG, PNG ou PDF</span>
              </>
            )}
            <div className="row">
              <button type="button" onClick={() => folderInput.current?.click()}>Escolher pasta</button>
              <button type="button" onClick={() => zipInput.current?.click()}>Escolher .zip</button>
            </div>
            <input
              ref={folderInput}
              type="file"
              hidden
              multiple
              {...({ webkitdirectory: "" } as Record<string, string>)}
              onChange={(e) => e.target.files && adopt(filesFromInput(e.target.files))}
            />
            <input
              ref={zipInput}
              type="file"
              hidden
              accept=".zip"
              onChange={(e) => e.target.files && adopt(filesFromInput(e.target.files))}
            />
          </div>
        </Card>
        <Card>
          <label>
            Perfil do cliente
            {profiles.isLoading ? (
              <Loading />
            ) : (
              <select value={profile} onChange={(e) => setProfile(e.target.value)}>
                {profiles.data?.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            )}
          </label>
          <label>
            Nome do lote
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="opcional" />
          </label>
          <label>
            <span>Manifesto com a contagem declarada (CSV <code>document,pages</code>)</span>
            <input type="file" accept=".csv" onChange={(e) => setManifest(e.target.files?.[0] ?? null)} />
          </label>
          <label>
            <span>Numeração lida (<code>numbering.json</code>)</span>
            <input type="file" accept=".json" onChange={(e) => setNumbering(e.target.files?.[0] ?? null)} />
            {numbering && <span className="muted small">{numbering.name}</span>}
          </label>
          <ErrorBox error={error} />
          <button className="primary" disabled={!files.length || sending} onClick={send}>
            {sending ? "Enviando…" : "Analisar lote"}
          </button>
        </Card>
      </div>

      <h2>Lotes recentes</h2>
      {batches.isLoading && <Loading />}
      <ErrorBox error={batches.error} />
      <table className="table">
        <thead>
          <tr><th>Lote</th><th>Enviado</th><th>Situação</th><th>Veredito</th><th>Páginas</th></tr>
        </thead>
        <tbody>
          {batches.data?.map((b) => (
            <tr key={b.id}>
              <td><a href={href({ name: "batch", id: b.id })}>{b.name}</a></td>
              <td>{new Date(b.created_at).toLocaleString("pt-BR")}</td>
              <td>{{ queued: "Na fila", processing: "Processando", analyzed: "Analisado", failed: "Falhou" }[b.status]}</td>
              <td>{b.summary ? VERDICT_LABEL[b.summary.verdict] : "—"}</td>
              <td>{b.summary?.pages_total ?? b.progress.total}</td>
            </tr>
          ))}
          {batches.data?.length === 0 && (
            <tr><td colSpan={5} className="muted">Nenhum lote ainda.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
