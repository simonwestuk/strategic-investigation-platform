const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const dateTimeFmt = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  timeZone: "UTC",
});

/** Backend timestamps are UTC; some are serialised without an offset. */
export function parseUtc(value: string): Date {
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value);
  const isDateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  return new Date(hasZone || isDateOnly ? value : `${value}Z`);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = parseUtc(value);
  return Number.isNaN(d.getTime()) ? value : dateFmt.format(d);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = parseUtc(value);
  return Number.isNaN(d.getTime()) ? value : `${dateTimeFmt.format(d)} UTC`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-GB").format(n);
}

export function formatCost(usd: number): string {
  return `$${usd.toFixed(usd < 1 ? 3 : 2)}`;
}

/** "market_contraction" -> "Market contraction" */
export function humanise(value: string): string {
  const s = value.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function pluralise(n: number, singular: string, plural = `${singular}s`): string {
  return `${n} ${n === 1 ? singular : plural}`;
}
