// Estado do motor descoberto na partida (``GET /health``), disponível para as telas.
import { createContext, useContext } from "react";
import type { Health } from "./client";

export const EngineContext = createContext<Health | null>(null);

export function useEngine(): Health {
  const engine = useContext(EngineContext);
  if (!engine) throw new Error("useEngine fora de EngineContext");
  return engine;
}
