import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { lockConflict } from "./lock";

describe("trava por caixa", () => {
  it("reconhece a caixa em conferência e se dá para assumir", () => {
    const err = new ApiError(409, "caixa em conferência", "Caixa 0412 em conferência por ana", [], { lock: { box: "0412" }, stale: true });
    expect(lockConflict(err)).toEqual({ detail: "Caixa 0412 em conferência por ana", stale: true });
    expect(lockConflict(new ApiError(409, "outro conflito"))).toBeNull();
    expect(lockConflict(new Error("x"))).toBeNull();
  });
});
