// Server-Sent Events via fetch (EventSource não envia o cabeçalho Authorization).
import { raw } from "./client";

export interface SseEvent {
  event: string;
  data: string;
}

/** Separa um buffer em eventos completos e devolve o resto ainda incompleto. */
export function parseSse(buffer: string): { events: SseEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: SseEvent[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":")) continue;
      const idx = line.indexOf(":");
      const field = idx === -1 ? line : line.slice(0, idx);
      const value = idx === -1 ? "" : line.slice(idx + 1).replace(/^ /, "");
      if (field === "event") event = value;
      else if (field === "data") data.push(value);
    }
    if (data.length) events.push({ event, data: data.join("\n") });
  }
  return { events, rest };
}

export async function streamEvents(
  path: string,
  onEvent: (e: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await raw(path, { signal, headers: { Accept: "text/event-stream" } });
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSse(buffer);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
}
