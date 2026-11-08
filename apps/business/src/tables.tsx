import type { FloorTable } from "@dinemate/api-client";
import { cx } from "@dinemate/ui";

export const SOON_MIN = 10;

export function minutesSince(iso: string | null, now: number): number | null {
  return iso ? Math.max(0, Math.round((now - Date.parse(iso)) / 60_000)) : null;
}

export function isSoon(t: FloorTable): boolean {
  return t.state === "occupied" && t.estimate !== null && t.estimate.high_min <= SOON_MIN;
}

export function estimateText(t: FloorTable): string | null {
  if (!t.estimate) return null;
  return t.estimate.low_min === 0 ? `~${t.estimate.high_min} min or less` : `~${t.estimate.low_min}–${t.estimate.high_min} min`;
}

export interface TableLook {
  className: string;
  title: string;
  detail: string;
  word: string;
}

export function tableLook(t: FloorTable, now: number): TableLook {
  const since = minutesSince(t.since, now);
  switch (t.state) {
    case "free":
      return { className: "border-2 border-ok-mark bg-ok-bg text-ok", title: `${t.seats} seats`, detail: "Free", word: "Free now" };
    case "occupied":
      return {
        className: cx(
          "bg-brand text-on-dark shadow-[0_4px_0_var(--color-brand-dark)]",
          isSoon(t) && "outline outline-[3px] outline-purple",
        ),
        title: `${t.party_size}/${t.seats}`,
        detail: isSoon(t) ? (estimateText(t) ?? "") : `${t.seated_min ?? 0} min`,
        word: isSoon(t) ? `Likely free ${estimateText(t)}` : "Seated",
      };
    case "held":
      return {
        className: "held-stripes border-2 border-busy-mark text-busy",
        title: "Held",
        detail: `bag · ${since ?? 0} min`,
        word: "Held by a bag",
      };
    case "needs_clearing":
      return {
        className: "border-2 border-dashed border-dash bg-card text-muted",
        title: "Clear",
        detail: `${since ?? 0} min`,
        word: "Needs clearing",
      };
    default:
      return {
        className: "border-2 border-dotted border-dash bg-page text-muted",
        title: "No view",
        detail: "—",
        word: "Camera can't see it",
      };
  }
}

export function tableSummary(t: FloorTable, now: number): string {
  const look = tableLook(t, now);
  if (t.state === "occupied") {
    const est = estimateText(t);
    return `${t.name}: seated, ${t.party_size} of ${t.seats} seats, ${t.seated_min ?? 0} min${est ? `, likely free in ${est}` : ""}`;
  }
  return `${t.name}: ${look.word.toLowerCase()}, ${t.seats} seats`;
}

export const LEGEND: { key: string; label: string; className: string }[] = [
  { key: "free", label: "Free", className: "border-2 border-ok-mark bg-ok-bg" },
  { key: "occupied", label: "Seated", className: "bg-brand" },
  { key: "soon", label: "Free soon", className: "bg-brand outline outline-2 outline-purple" },
  { key: "held", label: "Held by a bag", className: "held-stripes border-2 border-busy-mark" },
  { key: "clear", label: "Needs clearing", className: "border-2 border-dashed border-dash bg-card" },
];

export function urgency(t: FloorTable): number {
  if (t.state === "needs_clearing") return 0;
  if (isSoon(t)) return 1;
  if (t.state === "held") return 2;
  if (t.state === "unknown") return 3;
  if (t.state === "free") return 4;
  return 5;
}
