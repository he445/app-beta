import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { desktopApi, takeFragmentCode } from "./desktop";

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

describe("desktopApi", () => {
  type FakeWindow = EventTarget & { pywebview?: { api?: Record<string, unknown> } };
  let fake: FakeWindow;
  const api = { get_session: async () => ({ token: "t" }), pick_folder: async () => null };

  beforeEach(() => {
    vi.useFakeTimers();
    fake = new EventTarget() as FakeWindow;
    vi.stubGlobal("window", fake);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("fora da janela, desiste no prazo curto", async () => {
    const result = desktopApi(3000);
    await vi.advanceTimersByTimeAsync(3000);
    await expect(result).resolves.toBeNull();
  });

  it("api vazia ainda não é ponte: espera o pywebviewready", async () => {
    fake.pywebview = { api: {} };
    const result = desktopApi(3000);
    await vi.advanceTimersByTimeAsync(1000);
    fake.pywebview.api = api;
    fake.dispatchEvent(new Event("pywebviewready"));
    await expect(result).resolves.toBe(api);
  });

  it("com a pywebview na página, espera além dos 3 s (computador lento)", async () => {
    fake.pywebview = { api: {} };
    const result = desktopApi(3000, 30000);
    await vi.advanceTimersByTimeAsync(10000);
    fake.pywebview.api = api;
    fake.dispatchEvent(new Event("pywebviewready"));
    await expect(result).resolves.toBe(api);
  });

  it("api já pronta volta na hora", async () => {
    fake.pywebview = { api };
    await expect(desktopApi()).resolves.toBe(api);
  });
});
