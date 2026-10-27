import type { MealStatus, MealWindow, WeekDay } from "@dinemate/api-client";
import { cx, formatCountdown, formatRange, formatWeekday, Icon, SampleBadge } from "@dinemate/ui";
import { Footnote, Loading, MessageCard, Skeleton } from "../components/common";
import { MealBadge, mealBadgeText, useMealCountdown } from "../components/meal";
import { PERIOD_ICON, PERIOD_LABEL, startsLabel, windowProgress, windowState } from "../lib/present";

const FAR_AWAY_MS = 6 * 3_600_000;

function Countdown({ data, now, remaining }: { data: MealStatus; now: number; remaining: number | null }) {
  const { current, next } = data;
  const focus = current ?? next;
  const progress = current ? windowProgress(current, now) : 0;
  const far = !current && remaining !== null && remaining > FAR_AWAY_MS;
  return (
    <section aria-label="Meal countdown" className="flex flex-col items-center gap-3.5 rounded-3xl bg-brand-dark px-[18px] py-[22px] text-white">
      <MealBadge text={mealBadgeText(current, next)} />
      {focus && remaining !== null ? (
        <>
          <div
            className="flex h-[196px] w-[196px] items-center justify-center rounded-full"
            style={{ background: `conic-gradient(var(--color-live) 0 ${progress}%, var(--color-track-dark) ${progress}% 100%)` }}
          >
            <div className="flex h-[170px] w-[170px] flex-col items-center justify-center gap-1 rounded-full bg-brand-dark text-center">
              {far ? (
                <>
                  <span className="text-[28px] font-extrabold tracking-[-0.02em]">{startsLabel(focus, now)}</span>
                  <span className="text-[13px] text-on-dark">{PERIOD_LABEL[focus.period].toLowerCase()} starts</span>
                </>
              ) : (
                <>
                  <span className="tabular text-[34px] font-extrabold tracking-[-0.02em]">{formatCountdown(remaining)}</span>
                  <span className="text-[13px] text-on-dark">
                    until {PERIOD_LABEL[focus.period].toLowerCase()} {current ? "ends" : "starts"}
                  </span>
                </>
              )}
            </div>
          </div>
          <span className="text-sm text-on-dark-strong">{formatRange(focus.starts, focus.ends)}</span>
        </>
      ) : (
        <span className="py-6 text-lg font-bold">No meals scheduled this week</span>
      )}
    </section>
  );
}

function TodayRow({ window, now }: { window: MealWindow; now: number }) {
  const state = windowState(window, now);
  return (
    <li className={cx("flex items-center gap-3 rounded-[14px] p-2.5", state.kind === "now" && "bg-mint-soft")}>
      <span
        className={cx(
          "flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px]",
          state.kind === "ended" && "bg-neutral text-muted",
          state.kind === "now" && "bg-brand text-white",
          state.kind === "upcoming" && "bg-busy-bg text-busy",
        )}
      >
        <Icon name={PERIOD_ICON[window.period]} size={20} />
      </span>
      <span className="flex flex-1 flex-col">
        <span className={cx("text-[15px] font-extrabold", state.kind === "ended" && "text-neutral-ink")}>{PERIOD_LABEL[window.period]}</span>
        <span className={cx("text-xs", state.kind === "now" ? "text-ink-2" : "text-muted")}>{formatRange(window.starts, window.ends)}</span>
      </span>
      <span
        className={cx(
          "rounded-full px-2.5 py-1 text-xs",
          state.kind === "ended" && "bg-neutral font-bold text-neutral-ink",
          state.kind === "now" && "bg-card font-extrabold text-ok",
          state.kind === "upcoming" && "bg-busy-bg font-extrabold text-busy",
        )}
      >
        {state.kind === "ended" ? "Ended" : state.kind === "now" ? "Now serving" : state.inText}
      </span>
    </li>
  );
}

function DayCell({ day }: { day: WeekDay }) {
  return (
    <li
      aria-current={day.is_today ? "date" : undefined}
      className={cx(
        "flex flex-col items-center gap-1 rounded-xl py-2",
        day.is_today && "bg-brand text-white",
        !day.is_today && day.kind === "regular" && "border border-line bg-card",
        !day.is_today && day.kind === "special" && "border border-busy-line bg-busy-bg",
        !day.is_today && day.kind === "closed" && "border border-dashed border-dash bg-page",
      )}
    >
      <span className={cx("text-[11px]", day.is_today ? "text-on-dark-strong" : day.kind === "special" ? "text-busy" : "text-muted")}>{day.weekday}</span>
      <span
        className={cx(
          "text-[15px] font-extrabold",
          !day.is_today && day.kind === "special" && "text-busy",
          !day.is_today && day.kind === "closed" && "text-neutral-ink",
        )}
      >
        {day.day}
      </span>
      <span className="sr-only">{day.kind === "regular" ? "regular hours" : (day.note ?? "")}</span>
    </li>
  );
}

export function MealsScreen() {
  const { meal, now, remaining } = useMealCountdown();
  const data = meal.data;
  const special = data?.week.filter((d) => d.kind !== "regular" && d.note) ?? [];
  return (
    <div className="mx-auto flex w-full max-w-[720px] flex-1 flex-col md:pt-4">
      <header className="flex items-end justify-between gap-3 px-4 pb-2.5 pt-[18px] md:px-6">
        <div className="flex flex-col gap-0.5">
          <span className="text-[13px] text-muted">Today · {formatWeekday(now)}</span>
          <h1 className="m-0 text-2xl font-extrabold tracking-[-0.02em] md:text-[32px] md:tracking-[-0.03em]">Meal times</h1>
        </div>
        {data?.is_sample ? <SampleBadge>SAMPLE SCHEDULE</SampleBadge> : null}
      </header>
      <main id="main" className="flex flex-1 flex-col gap-3.5 px-4 pb-4 pt-1 md:px-6 md:pb-10">
        {!data ? (
          meal.isError ? (
            <MessageCard icon="wifiOff" title="Couldn't load meal times" body="Retrying automatically…" />
          ) : (
            <Loading label="Loading meal times">
              <Skeleton className="h-[300px] rounded-3xl" />
              <Skeleton className="h-[200px]" />
            </Loading>
          )
        ) : (
          <>
            <Countdown data={data} now={now} remaining={remaining} />
            <section aria-label="Today's meals" className="rounded-[20px] border border-line bg-card p-1.5">
              {data.today.length > 0 ? (
                <ul className="m-0 flex list-none flex-col gap-1 p-0">
                  {data.today.map((w) => (
                    <TodayRow key={w.period} window={w} now={now} />
                  ))}
                </ul>
              ) : (
                <p className="m-0 p-3 text-sm text-muted">No meals today — canteens closed.</p>
              )}
            </section>
            <section aria-labelledby="week-title" className="flex flex-col gap-2.5">
              <h2 id="week-title" className="m-0 text-[17px] font-extrabold">
                This week
              </h2>
              <ol className="m-0 grid list-none grid-cols-7 gap-1.5 p-0">
                {data.week.map((d) => (
                  <DayCell key={d.date} day={d} />
                ))}
              </ol>
              {special.length > 0 ? (
                <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-xs text-ink-2">
                  {special.map((d) => (
                    <li key={d.date} className="inline-flex items-center gap-2">
                      <span
                        className={cx(
                          "h-2.5 w-2.5 shrink-0 rounded-[3px]",
                          d.kind === "special" ? "border border-busy-mark bg-busy-bg" : "border border-dashed border-muted",
                        )}
                      />
                      {d.weekday}: {d.note}
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
            <Footnote>Shop hours can differ from meal times. Times shown in Sri Lanka time.</Footnote>
          </>
        )}
      </main>
    </div>
  );
}
