// Períodos da tela de Gestão (dia, semana, mês), em hora local, como intervalo [início, fim).
export type PeriodKind = "day" | "week" | "month";

export interface Period {
  since: Date;
  until: Date;
}

/** O dia, a semana (segunda a domingo) ou o mês que contém ``ref``, deslocado ``offset`` períodos. */
export function periodRange(kind: PeriodKind, ref: Date, offset = 0): Period {
  const since = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
  if (kind === "day") {
    since.setDate(since.getDate() + offset);
    const until = new Date(since);
    until.setDate(until.getDate() + 1);
    return { since, until };
  }
  if (kind === "week") {
    const fromMonday = (since.getDay() + 6) % 7;
    since.setDate(since.getDate() - fromMonday + 7 * offset);
    const until = new Date(since);
    until.setDate(until.getDate() + 7);
    return { since, until };
  }
  const start = new Date(ref.getFullYear(), ref.getMonth() + offset, 1);
  return { since: start, until: new Date(start.getFullYear(), start.getMonth() + 1, 1) };
}

/** Texto do período: "12/11/2026", "09/11 a 15/11/2026", "novembro de 2026". */
export function periodLabel(kind: PeriodKind, period: Period): string {
  if (kind === "day") return period.since.toLocaleDateString("pt-BR");
  if (kind === "month") return period.since.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  const last = new Date(period.until);
  last.setDate(last.getDate() - 1);
  const first = period.since.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  return `${first} a ${last.toLocaleDateString("pt-BR")}`;
}
