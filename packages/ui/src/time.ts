export const TIME_ZONE = "Asia/Colombo";

type TimeInput = string | number | Date;

const hmFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const dateLineFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: TIME_ZONE,
  weekday: "long",
  day: "numeric",
  month: "short",
  year: "numeric",
});

const weekdayFormat = new Intl.DateTimeFormat("en-GB", { timeZone: TIME_ZONE, weekday: "long" });

const stampFormat = new Intl.DateTimeFormat("en-GB", { timeZone: TIME_ZONE, weekday: "short", day: "numeric", month: "short" });

function toMs(value: TimeInput): number {
  if (typeof value === "number") return value;
  if (value instanceof Date) return value.getTime();
  return Date.parse(value);
}

function partsOf(value: TimeInput): { hour: number; minute: number } {
  const parts = Object.fromEntries(hmFormat.formatToParts(new Date(toMs(value))).map((p) => [p.type, p.value]));
  return { hour: Number(parts.hour), minute: Number(parts.minute) };
}

function twelveHour(hour: number, minute: number, withPeriod = true): string {
  const h = hour % 12 === 0 ? 12 : hour % 12;
  const time = `${h}:${String(minute).padStart(2, "0")}`;
  return withPeriod ? `${time} ${hour < 12 ? "a.m." : "p.m."}` : time;
}

function parseHM(hm: string): { hour: number; minute: number } {
  const [h = "0", m = "0"] = hm.split(":");
  return { hour: Number(h), minute: Number(m) };
}

export function formatClock(value: TimeInput): string {
  const { hour, minute } = partsOf(value);
  return twelveHour(hour, minute);
}

export function formatClock24(value: TimeInput): string {
  const { hour, minute } = partsOf(value);
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

export function formatLocalHM(hm: string): string {
  const { hour, minute } = parseHM(hm);
  return twelveHour(hour, minute);
}

function rangeOf(start: { hour: number; minute: number }, end: { hour: number; minute: number }, spaced: boolean): string {
  const samePeriod = start.hour < 12 === end.hour < 12;
  const dash = spaced ? " – " : "–";
  const first = twelveHour(start.hour, start.minute, !samePeriod);
  return `${first}${dash}${twelveHour(end.hour, end.minute)}`;
}

export function formatRange(start: TimeInput, end: TimeInput, spaced = true): string {
  return rangeOf(partsOf(start), partsOf(end), spaced);
}

export function formatLocalRange(opens: string, closes: string, spaced = false): string {
  const start = parseHM(opens);
  const end = parseHM(closes);
  const dash = spaced ? " – " : "–";
  return `${twelveHour(start.hour, start.minute)}${dash}${twelveHour(end.hour, end.minute)}`;
}

export function formatAgo(value: TimeInput | null, now: number): string {
  if (value === null) return "no readings yet";
  const seconds = Math.max(0, Math.round((now - toMs(value)) / 1000));
  if (seconds < 60) return `${seconds} s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  return `${Math.floor(minutes / 60)} h ago`;
}

export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

export function formatIn(ms: number): string {
  const minutes = Math.max(0, Math.round(ms / 60_000));
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

export function formatMinutes(ms: number): string {
  return `${Math.max(0, Math.round(ms / 60_000))} min`;
}

export function formatDateLine(value: TimeInput): string {
  const parts = Object.fromEntries(dateLineFormat.formatToParts(new Date(toMs(value))).map((p) => [p.type, p.value]));
  return `${parts.weekday}, ${parts.day} ${parts.month} ${parts.year}`;
}

export function formatWeekday(value: TimeInput): string {
  return weekdayFormat.format(new Date(toMs(value)));
}

export function formatDayStamp(value: TimeInput): string {
  const parts = Object.fromEntries(stampFormat.formatToParts(new Date(toMs(value))).map((p) => [p.type, p.value]));
  return `${parts.weekday} ${parts.day} ${parts.month} · ${formatClock(value)}`;
}

export function greeting(value: TimeInput): string {
  const { hour } = partsOf(value);
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export function formatPrice(lkr: number): string {
  return `Rs. ${lkr.toLocaleString("en-LK")}`;
}

export function msUntil(value: TimeInput, now: number): number {
  return toMs(value) - now;
}
