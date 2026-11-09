import type { AreaMinutes, StaffMethod } from "@dinemate/api-client";
import { cx } from "@dinemate/ui";

export const AREAS: { key: keyof AreaMinutes; label: string; bar: string; dot: string }[] = [
  { key: "counter", label: "Counter", bar: "bg-brand", dot: "bg-brand" },
  { key: "kitchen", label: "Kitchen", bar: "bg-purple", dot: "bg-purple" },
  { key: "floor", label: "Floor", bar: "bg-ok-mark", dot: "bg-ok-mark" },
];

export function hoursMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

export function totalMinutes(m: AreaMinutes): number {
  return m.counter + m.kitchen + m.floor;
}

export function AreaBar({ minutes, scale }: { minutes: AreaMinutes; scale: number }) {
  const total = totalMinutes(minutes);
  return (
    <span aria-hidden="true" className="flex h-2.5 min-w-[80px] flex-1 overflow-hidden rounded-full bg-track">
      {AREAS.map((a) => (
        <span
          key={a.key}
          className={cx("block h-full", a.bar)}
          style={{ width: `${(minutes[a.key] / Math.max(scale, total, 1)) * 100}%` }}
        />
      ))}
    </span>
  );
}

export function AreaLegend() {
  return (
    <span className="flex flex-wrap gap-3 text-[13px] text-muted">
      {AREAS.map((a) => (
        <span key={a.key} className="flex items-center gap-1.5">
          <span aria-hidden="true" className={cx("h-2.5 w-2.5 rounded-full", a.dot)} />
          {a.label}
        </span>
      ))}
    </span>
  );
}

export function MethodChip({ method, badge }: { method: StaffMethod; badge?: number | null }) {
  return (
    <span className="whitespace-nowrap rounded-full bg-chip px-2 py-0.5 text-xs font-semibold text-neutral-ink">
      {method === "face" ? "Face" : `Badge${badge !== null && badge !== undefined ? ` ${badge}` : ""}`}
    </span>
  );
}

export function OwnerOnly({ what }: { what: string }) {
  return (
    <div className="flex max-w-xl rounded-2xl border border-dashed border-dash bg-card p-5 text-sm leading-relaxed text-ink-2">
      {what} is for the owner only. Staff data is kept to the people who need it, and every view is recorded.
    </div>
  );
}
