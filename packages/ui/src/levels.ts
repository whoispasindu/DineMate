import type { CrowdLevel, Freshness } from "@dinemate/api-client";
import type { IconName } from "./icons";

export interface LevelStyle {
  label: string;
  icon: IconName;
  pill: string;
  bar: string;
  mark: string;
}

export const LEVELS: Record<CrowdLevel, LevelStyle> = {
  normal: {
    label: "Seats available",
    icon: "checkCircle",
    pill: "bg-ok-bg text-ok",
    bar: "bg-ok-mark",
    mark: "var(--color-ok-mark)",
  },
  busy: {
    label: "Busy",
    icon: "users",
    pill: "bg-busy-bg text-busy",
    bar: "bg-busy-mark",
    mark: "var(--color-busy-mark)",
  },
  crowded: {
    label: "Crowded",
    icon: "warning",
    pill: "bg-crowd-bg text-crowd",
    bar: "bg-crowd-mark",
    mark: "var(--color-crowd-mark)",
  },
  near_capacity: {
    label: "Nearly full",
    icon: "ban",
    pill: "bg-full-bg text-full",
    bar: "bg-full-mark",
    mark: "var(--color-full-mark)",
  },
  unknown: {
    label: "No live data",
    icon: "question",
    pill: "bg-neutral text-neutral-ink outline outline-1 -outline-offset-1 outline-dashed outline-dash",
    bar: "bg-dash",
    mark: "var(--color-dash)",
  },
};

export function levelFor(level: CrowdLevel, freshness: Freshness): LevelStyle {
  return freshness === "live" ? LEVELS[level] : LEVELS.unknown;
}
