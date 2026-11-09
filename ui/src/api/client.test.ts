import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, NETWORK_ERROR, getSession, normalizeBase, raw, setSession } from "./client";
import { waitForEngine } from "../lib/wake";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("endereço do motor", () => {
  it("normaliza o que vem da publicação ou do revisor", () => {
    expect(normalizeBase("https://qa-motor.onrender.com/")).toBe("https://qa-motor.onrender.com");
    expect(normalizeBase(" qa-motor.onrender.com ")).toBe("https://qa-motor.onrender.com");
    expect(normalizeBase("http://localhost:8000//")).toBe("http://localhost:8000");
    expect(normalizeBase("/api/")).toBe("/api");
    expect(normalizeBase("")).toBe(""); // mesma origem
  });
});

describe("falhas de rede e de acesso", () => {
  it('traduz "Failed to fetch" numa mensagem que diz o que fazer', async () => {
    setSession({ base: "https://motor.exemplo", token: "", reviewer: "Maria" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = await raw("/batches").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(NETWORK_ERROR);
    expect((err as ApiError).message).toContain("Sem conexão com o motor");
    expect((err as ApiError).message).toContain("https://motor.exemplo");
    expect((err as ApiError).message).not.toContain("Failed to fetch");
  });

  it("401 no modo só com nome explica e não apaga o revisor", async () => {
    setSession({ base: "", token: "", reviewer: "Maria" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ title: "Não autorizado" }), { status: 401 })));
    const err = (await raw("/batches").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(401);
    expect(err.message).toContain("exige token");
    expect(getSession().reviewer).toBe("Maria");
  });

  it("502/503 do servidor acordando vira orientação", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>", { status: 503 })));
    const err = (await raw("/batches").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(503);
    expect(err.message).toContain("acordando");
  });
});

describe("espera o motor acordar", () => {
  it("tenta de novo até responder", async () => {
    let clock = 0;
    const attempts: number[] = [];
    const check = vi
      .fn()
      .mockRejectedValueOnce(new Error("dormindo"))
      .mockRejectedValueOnce(new Error("dormindo"))
      .mockResolvedValue({ status: "ok" });
    const result = await waitForEngine(check, {
      sleep: async (ms) => {
        clock += ms;
      },
      now: () => clock,
      onAttempt: (n) => attempts.push(n),
    });
    expect(result).toEqual({ status: "ok" });
    expect(check).toHaveBeenCalledTimes(3);
    expect(attempts).toEqual([1, 2]);
    expect(clock).toBe(1500); // 500 ms + 1000 ms
  });

  it("desiste no prazo e relança o último erro", async () => {
    let clock = 0;
    const check = vi.fn().mockRejectedValue(new Error("fora do ar"));
    await expect(
      waitForEngine(check, {
        timeoutMs: 10_000,
        sleep: async (ms) => {
          clock += ms;
        },
        now: () => clock,
      }),
    ).rejects.toThrow("fora do ar");
    expect(clock).toBe(10_000);
  });
});
