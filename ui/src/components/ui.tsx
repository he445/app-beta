import type { ReactNode } from "react";
import { usePageImage } from "../api/hooks";
import type { Severity } from "../api/types";
import { SEVERITY_LABEL } from "../lib/format";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`badge sev-${severity}`}>{SEVERITY_LABEL[severity]}</span>;
}

export function StateDot({ state }: { state: string }) {
  const label = { green: "Verde", yellow: "Amarelo", red: "Vermelho" }[state] ?? state;
  return <span className={`dot state-${state}`} title={label} aria-label={label} />;
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {title && <h2>{title}</h2>}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: string }) {
  return (
    <div className={`stat ${tone ? `tone-${tone}` : ""}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="error" role="alert">{error instanceof Error ? error.message : String(error)}</div>;
}

export function Loading({ label = "Carregando…" }: { label?: string }) {
  return <div className="loading">{label}</div>;
}

/** Miniatura autenticada da página (original ou versão corrigida). */
export function Thumb({
  pageId,
  width = 160,
  className = "",
  alt = "",
  variant = "original",
}: {
  pageId?: string;
  width?: number;
  className?: string;
  alt?: string;
  variant?: "original" | "corrected";
}) {
  const img = usePageImage(pageId, variant, width * 2);
  return (
    <div className={`thumb ${className}`} style={{ width }}>
      {img.data ? <img src={img.data} alt={alt} /> : <div className="thumb-placeholder">{img.isError ? "sem imagem" : ""}</div>}
    </div>
  );
}

export function Bar({ value, max, tone }: { value: number; max: number; tone?: string }) {
  const width = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="bar">
      <div className={`bar-fill ${tone ? `tone-${tone}` : ""}`} style={{ width: `${width}%` }} />
    </div>
  );
}
