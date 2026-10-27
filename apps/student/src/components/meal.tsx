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
  if (!data) return <Skeleton className="h-[66px] rounded-[18px]" />;
  const { current, next } = data;
  let label = "Meal times";
  let value = "No meals scheduled";
  if (current && remaining !== null) {
    label = `${PERIOD_LABEL[current.period]} is being served`;
    value = `Ends in ${formatCountdown(remaining)}`;
  } else if (next && remaining !== null) {
    label = `${PERIOD_LABEL[next.period]} is next`;
    value = remaining > FAR_AWAY_MS ? `Starts at ${startsLabel(next, now)}` : `Starts in ${formatCountdown(remaining)}`;
  }
  return (
    <Link to="/meals" className="flex items-center gap-3 rounded-[18px] bg-brand-dark px-3.5 py-3 text-white no-underline hover:text-white">
      <span className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl bg-brand-mid text-live-ink">
        <Icon name="utensils" size={20} />
      </span>
      <span className="flex flex-1 flex-col">
        <span className="text-xs font-semibold text-on-dark">{label}</span>
        <span className="tabular text-xl font-extrabold tracking-[-0.01em]">{value}</span>
      </span>
      {current && next ? (
        <span className="text-right text-xs text-on-dark">
          {PERIOD_LABEL[next.period]}
          <br />
          {startsLabel(next, now)}
        </span>
      ) : null}
    </Link>
  );
}

export function MealBadge({ text }: { text: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 self-start rounded-full bg-brand-mid px-3 py-[5px] text-xs font-extrabold text-live-ink">
      <span className="h-2 w-2 rounded-full bg-live" />
      {text}
    </span>
  );
}

export function mealBadgeText(
  current: { period: keyof typeof PERIOD_LABEL } | null,
  next: { period: keyof typeof PERIOD_LABEL } | null,
): string {
  if (current) return `${PERIOD_LABEL[current.period].toUpperCase()} · NOW SERVING`;
  if (next) return `NEXT · ${PERIOD_LABEL[next.period].toUpperCase()}`;
  return "NO MEALS SCHEDULED";
}

export function MealCountdownCard({ className }: { className?: string }) {
  const { meal, now, remaining } = useMealCountdown();
  const data = meal.data;
  if (!data) return <Skeleton className={cx("min-h-[320px] rounded-[26px]", className)} />;
  const { current, next } = data;
  const focus = current ?? next;
  return (
    <section aria-label="Meal countdown" className={cx("flex flex-col gap-4 rounded-[26px] bg-brand-dark p-6 text-white", className)}>
      <MealBadge text={mealBadgeText(current, next)} />
      {focus && remaining !== null ? (
        <div className="flex flex-col gap-0.5">
          <span className="text-sm text-on-dark">{current ? "Ends in" : "Starts in"}</span>
          <span className="tabular text-[44px] font-extrabold leading-tight tracking-[-0.03em]">{formatCountdown(remaining)}</span>
        </div>
      ) : (
        <span className="text-lg font-bold">No meals in the next week</span>
      )}
      {current ? (
        <div aria-hidden="true" className="h-2 overflow-hidden rounded bg-track-dark">
          <div className="h-full rounded bg-live" style={{ width: `${windowProgress(current, now)}%` }} />
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
                state.kind === "ended" && "text-on-dark-faint",
                state.kind === "now" && "font-bold",
                state.kind === "upcoming" && "text-on-dark-strong",
              )}
            >
              <span>
                {PERIOD_LABEL[w.period]} · {formatRange(w.starts, w.ends, false)}
              </span>
              <span>{state.kind === "ended" ? "Ended" : state.kind === "now" ? "Now" : state.inText}</span>
            </li>
          );
        })}
        {data.today.length === 0 ? <li className="text-on-dark-strong">No meals today — canteens closed</li> : null}
      </ul>
      <span className="mt-auto text-xs text-on-dark-faint">{data.is_sample ? "Sample schedule · " : ""}Sri Lanka time</span>
    </section>
  );
}
