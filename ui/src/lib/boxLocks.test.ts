import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import type { BoxLocks } from "../api/types";
import { boxLockedFrom, lockNotices } from "./boxLocks";

const lock = {
  box: "0412",
  reviewer: "fulano",
  machine: "MAQ-1",
  since: "2026-11-12T17:05:00+00:00",
  renewed_at: "2026-11-12T17:06:00+00:00",
  abandoned: false,
  message: "Caixa 0412 em conferência por fulano, na máquina MAQ-1, desde 14:05 de 12/11/2026.",
};

describe("boxLockedFrom", () => {
  it("lê as travas do 409", () => {
    const err = new ApiError(409, "Caixa em conferência noutra máquina", lock.message, [], {
      title: "x",
      status: 409,
      detail: lock.message,
      locks: [lock],
      can_take_over: false,
    });
    expect(boxLockedFrom(err)?.locks[0]?.machine).toBe("MAQ-1");
  });

  it("ignora outros erros", () => {
    expect(boxLockedFrom(new ApiError(409, "Lote original alterado"))).toBeNull();
    expect(boxLockedFrom(new Error("x"))).toBeNull();
  });
});

describe("lockNotices", () => {
  const base: BoxLocks = { enabled: true, shared_configured: true, boxes: [], events: [] };

  it("avisa a caixa assumida com nome e máquina", () => {
    const view: BoxLocks = {
      ...base,
      boxes: [
        {
          box: "0412",
          state: "lost",
          scope: "shared",
          acquired_at: lock.since,
          ended_at: "2026-11-12T17:30:00+00:00",
          holder: { ...lock, reviewer: "beltrana", machine: "MAQ-2" },
        },
      ],
    };
    const [notice] = lockNotices(view);
    expect(notice?.tone).toBe("bad");
    expect(notice?.text).toContain("beltrana, na máquina MAQ-2");
  });

  it("avisa quando a trava vale só aqui", () => {
    const local = { box: "0412", state: "held" as const, scope: "local" as const, acquired_at: lock.since };
    expect(lockNotices({ ...base, shared_configured: false, boxes: [local] })[0]?.text).toContain("reports_dir");
    expect(lockNotices({ ...base, boxes: [local] })[0]?.text).toContain("fora do ar");
    expect(lockNotices({ ...base, boxes: [{ ...local, scope: "shared" }] })).toEqual([]);
    expect(lockNotices({ ...base, enabled: false, boxes: [local] })).toEqual([]);
  });
});
