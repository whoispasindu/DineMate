import { useMealStatus, useServerNow } from "@dinemate/api-client";
import { cx, formatCountdown, formatRange, Icon } from "@dinemate/ui";
import { useEffect } from "react";
import { Link } from "react-router";
import { PERIOD_LABEL, startsLabel, windowProgress, windowState } from "../lib/present";
import { Skeleton } from "./common";

const FAR_AWAY_MS = 6 * 3_600_000;

export function useMealCountdown() {
  const meal = useMealStatus();
  const now = useServerNow(1000);
  const data = meal.data;
  const target = data?.current?.ends ?? data?.next?.starts ?? null;
  const remaining = target === null ? null : Date.parse(target) - now;
  const expired = remaining !== null && remaining <= 0;
  const { refetch } = meal;
  useEffect(() => {
    if (expired) void refetch();
  }, [expired, refetch]);
  return { meal, now, remaining: remaining === null ? null : Math.max(0, remaining) };
}

export function MealPill() {
  const { meal, now, remaining } = useMealCountdown();
  const data = meal.data;
  if (!data) return <Skeleton className="h-[70px] rounded-[18px]" />;
  const { current, next } = data;
  let label = "Meal times";
  let value: string | null = null;
  let note = "No meals scheduled";
  if (current && remaining !== null) {
    label = `${PERIOD_LABEL[current.period]} ends in`;
    value = formatCountdown(remaining);
  } else if (next && remaining !== null) {
    label = `${PERIOD_LABEL[next.period]} starts`;
    if (remaining > FAR_AWAY_MS) note = startsLabel(next, now);
    else value = formatCountdown(remaining);
  }
  return (
    <Link
      to="/meals"
      className="edge-ticket flex items-center justify-between gap-4 rounded-[18px] bg-sand px-4 py-3 text-ink no-underline"
    >
      <span className="flex flex-col">
        <span className="text-[13px] font-semibold text-muted">{label}</span>
        {value ? (
          <span className="tabular mt-0.5 font-mono text-[22px] font-bold tracking-[-0.02em]">{value}</span>
        ) : (
          <span className="mt-0.5 text-lg font-bold">{note}</span>
        )}
      </span>
      {current ? (
        <span aria-hidden="true" className="flex w-[132px] flex-col gap-1.5">
          <span className="h-1.5 overflow-hidden rounded-full bg-sand-deep">
            <span className="block h-full rounded-full bg-brand" style={{ width: `${windowProgress(current, now)}%` }} />
          </span>
          <span className="flex justify-between text-xs text-muted">
            <span>{formatRange(current.starts, current.ends, false).split("–")[0]}</span>
            <span>{formatRange(current.starts, current.ends, false).split("–")[1]}</span>
          </span>
        </span>
      ) : (
        <Icon name="arrowRight" size={18} className="text-muted" />
      )}
    </Link>
  );
}

export function MealBadge({ text, light }: { text: string; light?: boolean }) {
  return (
    <span
      className={cx(
        "inline-flex h-7 items-center gap-1.5 self-start rounded-full px-3 text-xs font-bold",
        light ? "bg-card text-ink" : "bg-white/10 text-sand",
      )}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", light ? "bg-brand" : "bg-sand")} />
      {text}
    </span>
  );
}

export function mealBadgeText(
  current: { period: keyof typeof PERIOD_LABEL } | null,
  next: { period: keyof typeof PERIOD_LABEL } | null,
): string {
  if (current) return `${PERIOD_LABEL[current.period]} is being served`;
  if (next) return `Next · ${PERIOD_LABEL[next.period]}`;
  return "No meals scheduled";
}

export function MealCountdownCard({ className }: { className?: string }) {
  const { meal, now, remaining } = useMealCountdown();
  const data = meal.data;
  if (!data) return <Skeleton className={cx("min-h-[320px] rounded-[26px]", className)} />;
  const { current, next } = data;
  const focus = current ?? next;
  return (
    <section aria-label="Meal countdown" className={cx("edge-ticket flex flex-col gap-4 rounded-[26px] bg-sand p-6 text-ink", className)}>
      <MealBadge light text={mealBadgeText(current, next)} />
      {focus && remaining !== null ? (
        <div className="flex flex-col gap-0.5">
          <span className="text-sm text-muted">{current ? "Ends in" : "Starts in"}</span>
          <span className="tabular font-mono text-[44px] font-bold leading-tight tracking-[-0.05em]">{formatCountdown(remaining)}</span>
        </div>
      ) : (
        <span className="text-lg font-bold">No meals in the next week</span>
      )}
      {current ? (
        <div aria-hidden="true" className="h-2 overflow-hidden rounded bg-sand-deep">
          <div className="h-full rounded bg-brand" style={{ width: `${windowProgress(current, now)}%` }} />
        </div>
      ) : null}
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0 text-sm">
        {data.today.map((w) => {
          const state = windowState(w, now);
          return (
            <li
              key={w.period}
              className={cx(
                "flex justify-between gap-3",
                state.kind === "ended" && "text-muted",
                state.kind === "now" && "font-bold",
                state.kind === "upcoming" && "text-ink-2",
              )}
            >
              <span>
                {PERIOD_LABEL[w.period]} · {formatRange(w.starts, w.ends, false)}
              </span>
              <span>{state.kind === "ended" ? "Ended" : state.kind === "now" ? "Now" : state.inText}</span>
            </li>
          );
        })}
        {data.today.length === 0 ? <li className="text-ink-2">No meals today — canteens closed</li> : null}
      </ul>
      <span className="mt-auto text-xs text-muted">{data.is_sample ? "Sample schedule · " : ""}Sri Lanka time</span>
    </section>
  );
}
