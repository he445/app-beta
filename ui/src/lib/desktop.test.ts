import { describe, expect, it } from "vitest";
import { takeFragmentCode } from "./desktop";

describe("takeFragmentCode", () => {
  it("tira o código do fragmento e preserva a rota", () => {
    expect(takeFragmentCode("#code=abc_123")).toEqual({ code: "abc_123", rest: "" });
    expect(takeFragmentCode("#/batches/1&code=xyz")).toEqual({ code: "xyz", rest: "#/batches/1" });
    expect(takeFragmentCode("#code=xyz&outro=1")).toEqual({ code: "xyz", rest: "#outro=1" });
  });

  it("sem código, devolve o fragmento como está", () => {
    expect(takeFragmentCode("#/batches/1")).toEqual({ code: null, rest: "#/batches/1" });
    expect(takeFragmentCode("")).toEqual({ code: null, rest: "" });
  });
});
