// Estado do motor descoberto na partida (``GET /health``), disponível para as telas.
// As telas perguntam "o motor oferece X?" (capabilities), nunca "é desktop?": o mesmo
// build serve a nuvem, o programa desktop e o servidor interno.
import { createContext, useContext } from "react";
import type { Capability, Health } from "./types";

export const EngineContext = createContext<Health | null>(null);

export function useEngine(): Health {
  const engine = useContext(EngineContext);
  if (!engine) throw new Error("useEngine fora de EngineContext");
  return engine;
}

/** Se o motor oferece uma capacidade (``capabilities`` em ``/health``). */
export function hasCapability(engine: Health, capability: Capability): boolean {
  return engine.capabilities.includes(capability);
}

export function useCapability(capability: Capability): boolean {
  return hasCapability(useEngine(), capability);
}
