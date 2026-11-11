import { describe, expect, it } from "vitest";
import { screenOf } from "./report-error";

describe("screenOf", () => {
  it("tira os identificadores da rota", () => {
    expect(screenOf("#/batches/3f2a9c1e-1111-2222-3333-444455556666/review")).toBe("#/batches/:id/review");
    expect(screenOf("")).toBe("#/");
  });
});
