import { afterEach, describe, expect, it, vi } from "vitest";
import type { BulkCorrection, CorrectedDocument, CorrectedPlan } from "../api/types";
import { DOUBLE_CLICK_DELAY, createClickController } from "./clicks";
import {
  activeOperation,
  afterStrip,
  documentMarks,
  hasChanges,
  progressView,
  saveState,
  skippedText,
  mergeApplied,
  unsavedOperation,
  unsavedOperations,
} from "./corrections";
import { thumbnailKey, zoomModalKey } from "./keys";

function op(status: BulkCorrection["status"], done = 0, total = 0, extra: Partial<BulkCorrection> = {}): BulkCorrection {
  return {
    id: `op-${status}`,
    batch_id: "b",
    scope: { kind: "batch", id: "b" },
    status,
    progress: { done, total, current: status === "running" ? "CX001/DOC0001 · p. 4" : null },
    reviewer: "g1",
    started_at: "2026-11-08T10:00:00Z",
    ...extra,
  };
}

const page = (id: string, old: number, extra: Partial<CorrectedDocument["pages"][number]> = {}) => ({
  page_id: id, source_file: `${id}.tif`, source_page: 0, source_sha256: "0".repeat(64),
  old_position: old, new_position: old, target_file: `D/${String(old).padStart(4, "0")}.tif`, dpi: 300,
  status: "exported" as const, reason: null, corrected: false, moved: false, changes: [], needs_rescan: [],
  ...extra,
});

const missingGap = (decided: boolean): CorrectedDocument["missing"][number] => ({
  finding_id: "m1", missing: ["3"], after_page_id: "p2", before_page_id: "p3", after_position: 2,
  message: "Falta fls. 3.",
  decision: decided ? { action: "reject", decided_at: "2026-11-08T10:01:00Z", reviewer: "g1" } : null,
});

function plan(blocked: boolean): CorrectedPlan {
  return {
    batch_id: "b",
    can_save: !blocked,
    blockers: blocked ? [{ finding_id: "m1", document_id: "d2", document: "CX001/DOC0002", message: "x" }] : [],
    pending_critical: 1,
    pending_rescan: 1,
    unsaved_operations: [],
    documents: [],
  };
}

describe("clique simples × duplo clique", () => {
  afterEach(() => vi.useRealTimers());

  it("o clique simples só age depois do atraso", () => {
    vi.useFakeTimers();
    const single = vi.fn();
    const double = vi.fn();
    const c = createClickController(single, double);
    c.click("p1");
    vi.advanceTimersByTime(DOUBLE_CLICK_DELAY - 1);
    expect(single).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(single).toHaveBeenCalledWith("p1");
    expect(double).not.toHaveBeenCalled();
  });

  it("o duplo clique cancela o clique simples (nunca abre os dois)", () => {
    vi.useFakeTimers();
    const single = vi.fn();
    const double = vi.fn();
    const c = createClickController(single, double);
    c.click("p1"); // o navegador envia click, click, dblclick
    c.click("p1");
    c.doubleClick("p1");
    vi.advanceTimersByTime(1000);
    expect(double).toHaveBeenCalledTimes(1);
    expect(single).not.toHaveBeenCalled();
  });

  it("dois cliques espaçados são dois cliques simples", () => {
    vi.useFakeTimers();
    const single = vi.fn();
    const c = createClickController(single, vi.fn());
    c.click("a");
    vi.advanceTimersByTime(400);
    c.click("b");
    vi.advanceTimersByTime(400);
    expect(single.mock.calls).toEqual([["a"], ["b"]]);
  });

  it("cancelar descarta o clique pendente", () => {
    vi.useFakeTimers();
    const single = vi.fn();
    const c = createClickController(single, vi.fn());
    c.click("a");
    c.cancel();
    vi.advanceTimersByTime(1000);
    expect(single).not.toHaveBeenCalled();
  });
});

describe("teclado da sequência e do zoom", () => {
  it("miniatura: Enter abre a numeração e Z abre o zoom", () => {
    expect(thumbnailKey({ key: "Enter" })).toBe("numbering");
    expect(thumbnailKey({ key: "z" })).toBe("zoom");
    expect(thumbnailKey({ key: "Z" })).toBe("zoom");
    expect(thumbnailKey({ key: "z", ctrlKey: true })).toBeNull();
    expect(thumbnailKey({ key: "a" })).toBeNull();
  });
  it("modal: Esc fecha, setas passam de página, espaço amplia", () => {
    expect(zoomModalKey({ key: "Escape" })).toBe("close");
    expect(zoomModalKey({ key: "ArrowLeft" })).toBe("prev");
    expect(zoomModalKey({ key: "ArrowRight" })).toBe("next");
    expect(zoomModalKey({ key: " " })).toBe("zoom");
    expect(zoomModalKey({ key: "ArrowUp" })).toBeNull();
    expect(zoomModalKey({ key: "ArrowLeft", metaKey: true })).toBeNull();
  });
});

describe("Salvar correções", () => {
  it("fica bloqueado com página faltando sem decisão e explica o motivo", () => {
    const state = saveState(plan(true), [op("applied", 4, 4)]);
    expect(state.enabled).toBe(false);
    expect(state.reason).toContain("página faltando");
    expect(state.reason).toContain("CX001/DOC0002");
  });
  it("libera depois da decisão", () => {
    expect(saveState(plan(false), [op("applied", 4, 4)])).toEqual({ enabled: true, reason: null });
  });
  it("espera a correção em andamento e o plano carregar", () => {
    expect(saveState(plan(false), [op("running", 1, 4)]).enabled).toBe(false);
    expect(saveState(undefined, []).enabled).toBe(false);
  });
});

describe("tela de carregamento", () => {
  it("mostra cada estado com progresso real", () => {
    expect(progressView(undefined).finished).toBe(false);
    expect(progressView(op("queued", 0, 5))).toMatchObject({ title: "Na fila…", percent: 0, finished: false });
    const running = progressView(op("running", 2, 8));
    expect(running).toMatchObject({ title: "Corrigindo 2 de 8", percent: 25, finished: false, tone: "info" });
    expect(running.detail).toContain("p. 4");
    const done = progressView(op("applied", 8, 8, { result: { applied_total: 9, applied_by_rule: {}, skipped_total: 0, skipped: [], pages: [] } }));
    expect(done).toMatchObject({ percent: 100, finished: true, tone: "ok" });
    expect(done.title).toContain("9");
    expect(progressView(op("applied", 0, 0)).title).toBe("Nada automático para corrigir");
    expect(progressView(op("failed", 3, 8, { error: "disco cheio" }))).toMatchObject({ tone: "bad", finished: true, detail: "disco cheio" });
  });
});

describe("operações e faixa Depois", () => {
  it("encontra a operação ativa e a não salva que cobre o documento", () => {
    const result = { applied_total: 1, applied_by_rule: { skew: 1 }, skipped_total: 0, skipped: [], pages: [] };
    const docOp = op("applied", 1, 1, { id: "x", scope: { kind: "document", id: "d1" }, result });
    expect(activeOperation([op("saved"), op("running", 1, 2)])?.status).toBe("running");
    expect(unsavedOperation([docOp], "d1")?.id).toBe("x");
    expect(unsavedOperation([docOp], "d2")).toBeUndefined();
    expect(unsavedOperation([op("applied", 1, 1, { result })], "d2")?.status).toBe("applied");
    expect(unsavedOperation([op("applied", 0, 0)], "d2")).toBeUndefined(); // nada aplicado: nada a salvar
    const both = unsavedOperations([op("applied", 1, 1, { id: "b1", result }), docOp], "d1");
    expect(both.map((o) => o.id)).toEqual(["b1", "x"]);
    expect(mergeApplied(both)).toEqual({ skew: 2 });
  });

  it("ordena a faixa Depois pela posição final e ignora removidas", () => {
    const doc: CorrectedDocument = {
      document_id: "d1", name: "D", folder: "D", reordered: true, missing: [missingGap(false)],
      pages: [
        page("p1", 1),
        page("p2", 2, { status: "removed", new_position: null, target_file: null, reason: "em branco" }),
        page("p3", 3, { new_position: 3, moved: true }),
        page("p4", 4, { new_position: 2, moved: true, corrected: true }),
        page("p5", 5, { needs_rescan: [{ finding_id: "f", rule: "blur", text: "x" }], new_position: 4 }),
      ],
    };
    expect(afterStrip(doc).map((p) => p.page_id)).toEqual(["p1", "p4", "p3", "p5"]);
    expect(hasChanges(doc)).toBe(true);
    expect(documentMarks(doc)).toEqual({ changes: 3, missingPending: 1, rescan: 1 });
  });

  it("resume o que ficou pendente só do documento", () => {
    const result = {
      applied_total: 1, applied_by_rule: { skew: 1 }, skipped_total: 2, pages: [],
      skipped: [
        { finding_id: "a", rule: "missing_page", severity: "critical" as const, target: { kind: "document" as const, id: "d2" }, category: "missing_page" as const, reason: "" },
        { finding_id: "b", rule: "blur", severity: "critical" as const, target: { kind: "page" as const, id: "p9" }, category: "needs_rescan" as const, reason: "" },
      ],
    };
    const done = op("applied", 1, 1, { result });
    expect(skippedText(done, new Set(["d2"]))).toBe("1 página faltando (decida abaixo)");
    expect(skippedText(done)).toBe("1 página faltando (decida abaixo) · 1 precisa redigitalizar");
  });
});
