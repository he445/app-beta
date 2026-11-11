import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, blobUrl, download, getSession, json } from "./client";
import type {
  Analysis,
  BatchStatus,
  BulkCorrection,
  CorrectedBatch,
  CorrectedPlan,
  DecisionAction,
  DecisionResponse,
  MetadataField,
  NumberingResponse,
  Profile,
} from "./types";

export const keys = {
  batches: ["batches"] as const,
  batch: (id: string) => ["batch", id] as const,
  report: (id: string) => ["report", id] as const,
  profiles: ["profiles"] as const,
  plan: (id: string) => ["plan", id] as const,
  operations: (id: string) => ["operations", id] as const,
  image: (page: string, variant: string, width?: number) => ["image", page, variant, width] as const,
};

export function useBatches() {
  return useQuery({ queryKey: keys.batches, queryFn: () => api<BatchStatus[]>("/batches") });
}

export function useBatch(id: string) {
  return useQuery({
    queryKey: keys.batch(id),
    queryFn: () => api<BatchStatus>(`/batches/${id}`),
    refetchInterval: (q) => (q.state.data && isRunning(q.state.data) ? 2000 : false),
  });
}

export function isRunning(b: BatchStatus): boolean {
  return b.status === "queued" || b.status === "processing";
}

export function useReport(id: string, enabled = true) {
  return useQuery({
    queryKey: keys.report(id),
    queryFn: () => api<Analysis>(`/batches/${id}/report`),
    enabled,
    staleTime: 60_000,
  });
}

export function useProfiles() {
  return useQuery({ queryKey: keys.profiles, queryFn: () => api<Profile[]>("/profiles") });
}

/** Imagem autenticada como URL de objeto (img/OpenSeadragon não enviam o token). */
export function usePageImage(pageId: string | undefined, variant = "original", width?: number) {
  const query = width ? `?variant=${variant}&max_width=${width}` : `?variant=${variant}`;
  return useQuery({
    queryKey: keys.image(pageId ?? "", variant, width),
    queryFn: () => blobUrl(`/pages/${pageId}/image${query}`),
    enabled: Boolean(pageId),
    staleTime: Infinity,
    gcTime: 10 * 60_000,
    retry: false,
  });
}

function patchReport(qc: ReturnType<typeof useQueryClient>, batchId: string, fn: (r: Analysis) => Analysis) {
  qc.setQueryData<Analysis>(keys.report(batchId), (old) => (old ? fn(old) : old));
}

function reviewer(): string {
  return getSession().reviewer || "revisor";
}

/** Depois de qualquer mudança nas correções: relatório, plano e cópias corrigidas mudam. */
export function invalidateCorrections(qc: ReturnType<typeof useQueryClient>, batchId: string) {
  void qc.invalidateQueries({ queryKey: keys.report(batchId) });
  void qc.invalidateQueries({ queryKey: keys.plan(batchId) });
  void qc.invalidateQueries({ queryKey: keys.operations(batchId) });
  void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "image" && q.queryKey[2] === "corrected" });
}

export function usePlan(batchId: string, enabled = true) {
  return useQuery({
    queryKey: keys.plan(batchId),
    queryFn: () => api<CorrectedPlan>(`/batches/${batchId}/corrected-plan`),
    enabled,
  });
}

/**
 * Operações de "Corrigir tudo" do lote. Enquanto uma estiver em andamento, consulta o
 * progresso real a cada 400 ms; quando termina, recarrega relatório, plano e imagens.
 */
export function useBulkOperations(batchId: string) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: keys.operations(batchId),
    queryFn: () => api<BulkCorrection[]>(`/batches/${batchId}/bulk-corrections`),
    refetchInterval: (q) =>
      q.state.data?.some((op) => op.status === "queued" || op.status === "running") ? 400 : false,
  });
  const running = query.data?.some((op) => op.status === "queued" || op.status === "running") ?? false;
  const wasRunning = useRef(running);
  useEffect(() => {
    if (wasRunning.current && !running) invalidateCorrections(qc, batchId);
    wasRunning.current = running;
  }, [running, qc, batchId]);
  return query;
}

export function useStartBulk(batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (documentId?: string) =>
      json<BulkCorrection>(
        `/batches/${batchId}/bulk-corrections`,
        "POST",
        documentId ? { scope: "document", document_id: documentId, reviewer: reviewer() } : { scope: "batch", reviewer: reviewer() },
      ),
    onSuccess: (op) => {
      qc.setQueryData<BulkCorrection[]>(keys.operations(batchId), (old) => [op, ...(old ?? [])]);
    },
  });
}

export function useUndoBulk(batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (operationId: string) =>
      api<BulkCorrection>(`/bulk-corrections/${operationId}?reviewer=${encodeURIComponent(reviewer())}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateCorrections(qc, batchId),
  });
}

/** "Salvar correções": gera o lote corrigido; no .zip, baixa o arquivo; em pasta, grava em output_dir. */
export function useSaveCorrected(batchId: string, batchName: string, destination: "zip" | "folder" = "zip") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const saved = await json<CorrectedBatch>(`/batches/${batchId}/corrected-batch`, "POST", {
        reviewer: reviewer(),
        destination,
      });
      if (saved.download) await download(saved.download, `${batchName}-${saved.file}`);
      return saved;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.operations(batchId) });
      void qc.invalidateQueries({ queryKey: keys.plan(batchId) });
    },
  });
}

export function useDecide(batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ findingId, action }: { findingId: string; action: DecisionAction }) =>
      json<DecisionResponse>(`/findings/${findingId}/decision`, "POST", {
        action,
        reviewer: getSession().reviewer || "revisor",
      }),
    onSuccess: (res) => {
      patchReport(qc, batchId, (r) => ({
        ...r,
        batch: { ...r.batch, summary: res.summary },
        findings: r.findings.map((f) => (f.id === res.finding.id ? res.finding : f)),
      }));
      void qc.invalidateQueries({ queryKey: keys.plan(batchId) });
      void qc.invalidateQueries({ queryKey: ["image", res.finding.target.id, "corrected"] });
    },
  });
}

/** Rotação escolhida pelo revisor: giro horário total da página na cópia (0 = não girar). */
export function useRotate(batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pageId, angle }: { pageId: string; angle: number }) =>
      json<DecisionResponse>(`/pages/${pageId}/rotation`, "PUT", {
        angle_deg: angle,
        reviewer: getSession().reviewer || "revisor",
      }),
    onSuccess: (res) => {
      patchReport(qc, batchId, (r) => {
        const exists = r.findings.some((f) => f.id === res.finding.id);
        return {
          ...r,
          batch: { ...r.batch, summary: res.summary },
          findings: exists
            ? r.findings.map((f) => (f.id === res.finding.id ? res.finding : f))
            : [...r.findings, res.finding],
        };
      });
      void qc.invalidateQueries({ queryKey: keys.plan(batchId) });
      void qc.invalidateQueries({ queryKey: ["image", res.finding.target.id, "corrected"] });
    },
  });
}

export function useUndo(batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) =>
      api<DecisionResponse>(
        `/findings/${findingId}/decision?reviewer=${encodeURIComponent(getSession().reviewer || "revisor")}`,
        { method: "DELETE" },
      ),
    onSuccess: (res) => {
      patchReport(qc, batchId, (r) => ({
        ...r,
        batch: { ...r.batch, summary: res.summary },
        findings: r.findings.map((f) => (f.id === res.finding.id ? res.finding : f)),
      }));
      void qc.invalidateQueries({ queryKey: keys.plan(batchId) });
      void qc.invalidateQueries({ queryKey: ["image", res.finding.target.id, "corrected"] });
    },
  });
}

export function useSetNumbering(batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pageId, value }: { pageId: string; value: string }) =>
      json<NumberingResponse>(`/pages/${pageId}/numbering`, "PUT", {
        value,
        reviewer: getSession().reviewer || "revisor",
      }),
    // A numeração regenera as sinalizações de sequência: recarrega o relatório.
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.report(batchId) });
      void qc.invalidateQueries({ queryKey: keys.plan(batchId) });
    },
  });
}

export function useSetMetadata(batchId: string, documentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, value }: { name: string; value?: unknown }) =>
      json<MetadataField[]>(`/documents/${documentId}/metadata/${name}`, "PUT", {
        ...(value === undefined ? {} : { value }),
        reviewer: getSession().reviewer || "revisor",
      }),
    onSuccess: (fields) =>
      patchReport(qc, batchId, (r) => ({ ...r, metadata: { ...r.metadata, [documentId]: fields } })),
  });
}
