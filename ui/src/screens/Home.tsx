// Tela 1: abrir ou enviar lote, conforme o que o motor oferece. Também lista os lotes recentes.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, json, raw } from "../api/client";
import { useCapability, useEngine } from "../api/engine";
import { keys, useBatches, useProfiles } from "../api/hooks";
import type { BatchStatus } from "../api/types";
import { LocalBatchCard } from "../components/LocalBatchCard";
import { Card, ErrorBox, Loading } from "../components/ui";
import { canPickFolders, filesFromDrop, filesFromInput, isTouchDevice, type PickedFile } from "../lib/files";
import { VERDICT_LABEL } from "../lib/format";
import { href, navigate } from "../router";

interface DemoBatch {
  name: string;
  pages: number;
  documents: number;
}

/** Lote de demonstração pronto no servidor: o celular não precisa enviar nada (ADR-0010). */
function DemoBatchCard({ profile }: { profile: string }) {
  const engine = useEngine();
  const qc = useQueryClient();
  const demos = useQuery({
    queryKey: ["demo-batches"],
    queryFn: () => api<DemoBatch[]>("/demo-batches"),
    enabled: engine.demo_batches > 0,
  });
  const start = useMutation({
    mutationFn: (name: string) => json<BatchStatus>(`/demo-batches/${encodeURIComponent(name)}`, "POST", { profile_id: profile }),
    onSuccess: (status) => {
      void qc.invalidateQueries({ queryKey: keys.batches });
      navigate({ name: "batch", id: status.id });
    },
  });
  if (!engine.demo_batches || !demos.data?.length) return null;
  return (
    <Card title="Lote de demonstração" className="demo-card">
      <p className="small muted">
        Lote sintético já no servidor, com página faltando, página em branco, página torta e
        página sem nitidez. Nada é enviado do aparelho.
      </p>
      <div className="row wrap">
        {demos.data.map((d) => (
          <button key={d.name} className="primary" disabled={start.isPending} onClick={() => start.mutate(d.name)}>
            {start.isPending ? "Abrindo…" : `Analisar ${d.name} (${d.pages} páginas, ${d.documents} documentos)`}
          </button>
        ))}
      </div>
      <ErrorBox error={start.error} />
    </Card>
  );
}

const STATUS_LABEL: Record<BatchStatus["status"], string> = {
  queued: "Na fila",
  processing: "Processando",
  analyzed: "Analisado",
  failed: "Falhou",
};

const STAGE_LABEL: Record<NonNullable<BatchStatus["stage"]>, string> = {
  settling: "Esperando a pasta parar de mudar",
  snapshot: "Conferindo os arquivos",
  analyzing: "Analisando",
};

export function statusLabel(b: BatchStatus): string {
  if ((b.status === "queued" || b.status === "processing") && b.stage) return STAGE_LABEL[b.stage];
  return STATUS_LABEL[b.status];
}

export function Home() {
  const canUpload = useCapability("upload");
  const canOpenFolder = useCapability("local_batches");
  const syntheticOnly = useCapability("synthetic_only");
  const hasDemos = useCapability("demo_batches");
  const batches = useBatches();
  return (
    <div className="page">
      <h1>{canOpenFolder ? "Abrir lote" : "Enviar lote"}</h1>
      {canOpenFolder && <LocalBatchCard />}
      {hasDemos && <DemoBatchCard profile="demo" />}
      {syntheticOnly && (
        <div className="warning" role="note">
          <strong>Somente documentos sintéticos ou públicos.</strong> Documento de cliente é proibido neste
          servidor de demonstração. Os lotes são apagados automaticamente após 24 horas.
        </div>
      )}
      {canUpload && <UploadForm />}

      <h2>Lotes recentes</h2>
      {batches.isLoading && <Loading />}
      <ErrorBox error={batches.error} />
      <table className="table">
        <thead>
          <tr><th>Lote</th><th>Aberto em</th><th>Situação</th><th>Veredito</th><th>Páginas</th></tr>
        </thead>
        <tbody>
          {batches.data?.map((b) => (
            <tr key={b.id}>
              <td><a href={href({ name: "batch", id: b.id })}>{b.name}</a></td>
              <td>{new Date(b.created_at).toLocaleString("pt-BR")}</td>
              <td>{statusLabel(b)}</td>
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

/** Enviar lote pelo navegador (capacidade upload). */
function UploadForm() {
  const profiles = useProfiles();
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
  const imagesInput = useRef<HTMLInputElement>(null);
  const folders = canPickFolders();
  const touch = isTouchDevice();

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
                <strong>{touch ? "Escolha um .zip ou as imagens do lote" : "Arraste a pasta do lote ou um .zip"}</strong>
                <span className="muted">TIFF, JPG, PNG ou PDF</span>
              </>
            )}
            <div className="row wrap center">
              {folders && <button type="button" onClick={() => folderInput.current?.click()}>Escolher pasta</button>}
              <button type="button" onClick={() => zipInput.current?.click()}>Escolher .zip</button>
              <button type="button" onClick={() => imagesInput.current?.click()}>Escolher imagens</button>
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
              accept=".zip,application/zip"
              onChange={(e) => e.target.files && adopt(filesFromInput(e.target.files))}
            />
            <input
              ref={imagesInput}
              type="file"
              hidden
              multiple
              accept=".tif,.tiff,.jpg,.jpeg,.png,.pdf,image/*,application/pdf"
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
  );
}
