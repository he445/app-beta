import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, blobUrl, getSession, json } from "./client";
import type {
  Analysis,
  BatchStatus,
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
      if (res.applied) void qc.invalidateQueries({ queryKey: ["image", res.finding.target.id, "corrected"] });
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
    onSuccess: (res) =>
      patchReport(qc, batchId, (r) => ({
        ...r,
        batch: { ...r.batch, summary: res.summary },
        findings: r.findings.map((f) => (f.id === res.finding.id ? res.finding : f)),
      })),
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
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.report(batchId) }),
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
