// Tela 7: metadados por documento, com fonte e confiança, editáveis.
import { useState } from "react";
import { useReport, useSetMetadata } from "../api/hooks";
import type { MetadataField } from "../api/types";
import { ErrorBox, Loading, StateDot } from "../components/ui";
import { SOURCE_LABEL, formatValue, pct } from "../lib/format";
import { href } from "../router";

const LABEL: Record<string, string> = {
  scan_date: "Data da digitalização",
  scan_location: "Local da digitalização",
  responsible: "Responsável",
  identifier: "Identificador",
  hash_sha256: "Hash SHA-256",
  title: "Título",
  document_type: "Tipo documental",
  author: "Autor (emissor)",
  subject: "Assunto",
  make: "Fabricante",
  model: "Modelo",
  software: "Software",
  dpi: "Resolução (dpi)",
  color_mode: "Modo de cor",
  bit_depth: "Profundidade (bits)",
  compression: "Compressão",
  format: "Formato",
  page_count: "Páginas",
  size_bytes: "Tamanho (bytes)",
  width_mm: "Largura (mm)",
  height_mm: "Altura (mm)",
};

export function Metadata({ id, doc }: { id: string; doc?: string }) {
  const report = useReport(id);
  if (report.isLoading) return <Loading />;
  if (!report.data) return <div className="page"><ErrorBox error={report.error} /></div>;
  const r = report.data;
  const selected = r.documents.find((d) => d.id === doc) ?? r.documents[0];
  return (
    <div className="split">
      <aside className="doc-list">
        {r.documents.map((d) => (
          <a key={d.id} href={href({ name: "metadata", id, doc: d.id })} className={d.id === selected?.id ? "active" : ""}>
            <StateDot state={d.state} /> {d.name}
          </a>
        ))}
      </aside>
      <main className="page">
        {selected && (
          <>
            <h1>{selected.name}</h1>
            <p className="muted">
              Decreto 10.278/2020: os campos marcados como exigidos só valem depois de confirmados.
            </p>
            <Fields batchId={id} documentId={selected.id} fields={r.metadata[selected.id] ?? []} />
          </>
        )}
      </main>
    </div>
  );
}

function Fields({ batchId, documentId, fields }: { batchId: string; documentId: string; fields: MetadataField[] }) {
  const save = useSetMetadata(batchId, documentId);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const required = fields.filter((f) => f.required_by_decree);
  const technical = fields.filter((f) => !f.required_by_decree);

  function row(f: MetadataField) {
    const isEditing = editing === f.name;
    return (
      <tr key={f.name} className={f.confirmed ? "confirmed" : ""}>
        <th>{LABEL[f.name] ?? f.name}</th>
        <td className="value">
          {isEditing ? (
            <form
              className="row tight"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate({ name: f.name, value: draft }, { onSuccess: () => setEditing(null) });
              }}
            >
              <input value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus aria-label={LABEL[f.name] ?? f.name} />
              <button className="primary">Salvar</button>
              <button type="button" onClick={() => setEditing(null)}>Cancelar</button>
            </form>
          ) : (
            <span className="ellipsis" title={formatValue(f.value)}>{formatValue(f.value)}</span>
          )}
          {f.note && <div className="small muted">{f.note}</div>}
        </td>
        <td>{SOURCE_LABEL[f.source] ?? f.source}</td>
        <td className="num">{pct(f.confidence)}</td>
        <td>
          {f.confirmed ? (
            <span className="tag ok">confirmado</span>
          ) : (
            f.required_by_decree && (
              <div className="row tight">
                {f.value !== null && (
                  <button className="small-btn" onClick={() => save.mutate({ name: f.name })}>Confirmar</button>
                )}
                <button
                  className="small-btn"
                  onClick={() => {
                    setEditing(f.name);
                    setDraft(f.value === null ? "" : formatValue(f.value));
                  }}
                >
                  Editar
                </button>
              </div>
            )
          )}
        </td>
      </tr>
    );
  }

  return (
    <>
      <ErrorBox error={save.error} />
      <h2>Exigidos pelo Decreto (Anexo II)</h2>
      <table className="table meta">
        <thead><tr><th>Campo</th><th>Valor</th><th>Fonte</th><th>Confiança</th><th /></tr></thead>
        <tbody>{required.map(row)}</tbody>
      </table>
      <h2>Técnicos (Anexo I)</h2>
      <table className="table meta">
        <thead><tr><th>Campo</th><th>Valor</th><th>Fonte</th><th>Confiança</th><th /></tr></thead>
        <tbody>{technical.map(row)}</tbody>
      </table>
    </>
  );
}
