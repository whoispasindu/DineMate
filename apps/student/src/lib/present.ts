import type { CanteenSummary, MealPeriod, MealWindow, NoticeKind, ShopKind, ZoneOccupancy } from "@dinemate/api-client";
import { formatClock, formatIn, formatWeekday, type IconName } from "@dinemate/ui";

const CANTEEN_WALLS: Record<string, string> = {
  a: "#F6E7C8",
  b: "#DCEFE2",
  c: "#E2E5F4",
};

const FALLBACK_WALLS = ["#F6E7C8", "#DCEFE2", "#E2E5F4", "#FDE4DC"];

export function canteenWall(id: string): string {
  return CANTEEN_WALLS[id] ?? FALLBACK_WALLS[id.charCodeAt(0) % FALLBACK_WALLS.length] ?? "#DCEFE2";
}

export function canteenInitial(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  const last = words.at(-1) ?? "";
  if (/^[\p{L}\p{N}]{1,2}$/u.test(last)) return last.toUpperCase();
  return (words[0]?.match(/[\p{L}\p{N}]/u)?.[0] ?? "?").toUpperCase();
}

type Occupancy = Pick<CanteenSummary | ZoneOccupancy, "free_about" | "free_range" | "freshness">;

export function hasNumbers(o: Occupancy): o is Occupancy & { free_about: number; free_range: [number, number] } {
  return o.freshness !== "unavailable" && o.free_about !== null && o.free_range !== null;
}

export function freeShort(o: Occupancy): string {
  return hasNumbers(o) ? `~${o.free_about} free` : "No info right now";
}

export function rangeText(o: Occupancy): string {
  return hasNumbers(o) ? `(${o.free_range[0]}–${o.free_range[1]})` : "";
}

export const PERIOD_LABEL: Record<MealPeriod, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
};

export const PERIOD_ICON: Record<MealPeriod, IconName> = {
  breakfast: "breakfast",
  lunch: "utensils",
  dinner: "dinner",
};

export const PERIODS: MealPeriod[] = ["breakfast", "lunch", "dinner"];

export function startsLabel(window: MealWindow, now: number): string {
  const sameDay = formatWeekday(window.starts) === formatWeekday(now) && Date.parse(window.starts) - now < 86_400_000;
  return sameDay ? formatClock(window.starts) : `${formatWeekday(window.starts)} ${formatClock(window.starts)}`;
}

export type WindowState = { kind: "ended" } | { kind: "now" } | { kind: "upcoming"; inText: string };

export function windowState(window: MealWindow, now: number): WindowState {
  if (now >= Date.parse(window.ends)) return { kind: "ended" };
  if (now >= Date.parse(window.starts)) return { kind: "now" };
  return { kind: "upcoming", inText: `In ${formatIn(Date.parse(window.starts) - now)}` };
}

export function windowProgress(window: MealWindow, now: number): number {
  const start = Date.parse(window.starts);
  const end = Date.parse(window.ends);
  return Math.min(100, Math.max(0, Math.round(((now - start) / (end - start)) * 100)));
}

export const NOTICE_LOOK: Record<NoticeKind, { icon: IconName; tile: string }> = {
  crowding: { icon: "warning", tile: "bg-crowd-bg text-crowd" },
  data_unavailable: { icon: "question", tile: "bg-neutral text-neutral-ink" },
  sold_out: { icon: "soldOut", tile: "bg-busy-bg text-busy" },
  shop_closing: { icon: "clock", tile: "bg-busy-bg text-busy" },
  meal_starting: { icon: "utensils", tile: "bg-ok-bg text-ok" },
};

export const SHOP_LOOK: Record<ShopKind, { icon: IconName; tile: string }> = {
  rice: { icon: "bowl", tile: "bg-busy-bg text-busy" },
  kottu: { icon: "pan", tile: "bg-crowd-bg text-crowd" },
  short_eats: { icon: "bun", tile: "bg-indigo-bg text-indigo" },
  tea: { icon: "cup", tile: "bg-neutral text-neutral-ink" },
  noodles: { icon: "bowl", tile: "bg-ok-bg text-ok" },
  bakery: { icon: "bun", tile: "bg-busy-bg text-busy" },
  drinks: { icon: "cup", tile: "bg-indigo-bg text-indigo" },
};

export const ITEM_TINTS = ["bg-busy-bg text-busy", "bg-ok-bg text-ok", "bg-crowd-bg text-crowd", "bg-indigo-bg text-indigo"];
