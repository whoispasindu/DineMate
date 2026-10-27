const SAMPLE_CLOCK_START = Date.parse("2026-11-20T12:41:18+05:30");
const bootedAt = Date.now();
const DAY_MS = 86_400_000;
const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

const partsFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Colombo",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function sampleNow(): number {
  return SAMPLE_CLOCK_START + (Date.now() - bootedAt);
}

export function iso(ms: number): string {
  return new Date(ms).toISOString();
}

export function colomboDate(ms: number): string {
  const parts = Object.fromEntries(partsFormat.formatToParts(new Date(ms)).map((p) => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function colomboHM(ms: number): string {
  const parts = Object.fromEntries(partsFormat.formatToParts(new Date(ms)).map((p) => [p.type, p.value]));
  return `${parts.hour}:${parts.minute}`;
}

export function weekdayIndex(date: string): number {
  return (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7;
}

export function weekdayName(date: string): string {
  return WEEKDAY_NAMES[weekdayIndex(date)] ?? "";
}

export function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

export function atLocal(date: string, hm: string): number {
  return Date.parse(`${date}T${hm}:00+05:30`);
}

export function todayAt(now: number, hm: string): number {
  return atLocal(colomboDate(now), hm);
}

export function periodicReading(now: number, ageAtStartS: number, periodS: number): number {
  const elapsedS = (now - SAMPLE_CLOCK_START) / 1000 + ageAtStartS;
  const ageS = ((elapsedS % periodS) + periodS) % periodS;
  return now - ageS * 1000;
}

export function fixedReading(ageAtStartS: number): number {
  return SAMPLE_CLOCK_START - ageAtStartS * 1000;
}
