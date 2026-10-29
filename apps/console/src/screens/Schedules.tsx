import {
  apiMode,
  useCanteens,
  useMealSchedules,
  useSaveMealSchedules,
  useStaffSession,
  type MealOverride,
  type MealPeriod,
  type MealScheduleSet,
  type MealSlot,
} from "@dinemate/api-client";
import { cx } from "@dinemate/ui";
import { useEffect, useMemo, useState } from "react";
import { Banner, Button, errorText, Page, Panel, Select, TextInput, useUnsavedGuard } from "../kit";
import { WEEKDAYS } from "./ShopHours";

const PERIODS: MealPeriod[] = ["breakfast", "lunch", "dinner"];
const PERIOD_LABEL: Record<MealPeriod, string> = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner" };
const DEFAULT_TIMES: Record<MealPeriod, [string, string]> = {
  breakfast: ["07:00", "09:30"],
  lunch: ["11:30", "14:00"],
  dinner: ["18:00", "20:30"],
};

const hm = (value: string | null) => (value ?? "").slice(0, 5);
const campusDate = (iso: string) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Colombo" }).format(Date.parse(iso));

interface Draft {
  ownWeek: boolean;
  weekly: MealSlot[];
  overrides: MealOverride[];
}

function fromSet(set: MealScheduleSet): Draft {
  return {
    ownWeek: set.canteen_id === null || !set.uses_campus_weekly,
    weekly: set.weekly.map((s) => ({ ...s, starts: hm(s.starts), ends: hm(s.ends) })),
    overrides: set.overrides.map((o) => ({ ...o, starts: o.starts && hm(o.starts), ends: o.ends && hm(o.ends) })),
  };
}

function WeekGrid({ draft, setDraft, disabled }: { draft: Draft; setDraft: (d: Draft) => void; disabled: boolean }) {
  const find = (weekday: number, period: MealPeriod) => draft.weekly.findIndex((s) => s.weekday === weekday && s.period === period);
  const patch = (index: number, change: Partial<MealSlot>) =>
    setDraft({ ...draft, weekly: draft.weekly.map((s, i) => (i === index ? { ...s, ...change } : s)) });
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-muted">
            <th scope="col" className="border-b border-chip pb-2 font-semibold">
              Day
            </th>
            {PERIODS.map((p) => (
              <th key={p} scope="col" className="border-b border-chip px-2 pb-2 font-semibold">
                {PERIOD_LABEL[p]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {WEEKDAYS.map((day, weekday) => (
            <tr key={day} className="border-b border-line-soft">
              <th scope="row" className="py-2 pr-2 text-left font-bold">
                {day}
              </th>
              {PERIODS.map((period) => {
                const index = find(weekday, period);
                const slot = index >= 0 ? draft.weekly[index] : undefined;
                return (
                  <td key={period} className="px-2 py-2">
                    {slot ? (
                      <span className="inline-flex items-center gap-1">
                        <TextInput
                          type="time"
                          aria-label={`${day} ${period} starts`}
                          disabled={disabled}
                          value={slot.starts}
                          onChange={(e) => patch(index, { starts: e.target.value })}
                        />
                        <span className="text-muted">–</span>
                        <TextInput
                          type="time"
                          aria-label={`${day} ${period} ends`}
                          disabled={disabled}
                          value={slot.ends}
                          onChange={(e) => patch(index, { ends: e.target.value })}
                        />
                        {!disabled ? (
                          <Button
                            aria-label={`No ${period} on ${day}`}
                            className="min-h-9 px-2.5"
                            onClick={() => setDraft({ ...draft, weekly: draft.weekly.filter((_, i) => i !== index) })}
                          >
                            ×
                          </Button>
                        ) : null}
                      </span>
                    ) : disabled ? (
                      <span className="text-muted">—</span>
                    ) : (
                      <Button
                        className="min-h-9"
                        onClick={() =>
                          setDraft({
                            ...draft,
                            weekly: [
                              ...draft.weekly,
                              { weekday, period, starts: DEFAULT_TIMES[period][0], ends: DEFAULT_TIMES[period][1] },
                            ],
                          })
                        }
                      >
                        + {PERIOD_LABEL[period]}
                      </Button>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OverrideList({
  draft,
  setDraft,
  disabled,
  today,
}: {
  draft: Draft;
  setDraft: (d: Draft) => void;
  disabled: boolean;
  today: string;
}) {
  const patch = (index: number, change: Partial<MealOverride>) =>
    setDraft({ ...draft, overrides: draft.overrides.map((o, i) => (i === index ? { ...o, ...change } : o)) });
  return (
    <div className="flex flex-col gap-2.5">
      {draft.overrides.length === 0 ? <span className="text-sm text-muted">No date overrides.</span> : null}
      {draft.overrides.map((o, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2.5">
          <TextInput
            type="date"
            aria-label="Override date"
            disabled={disabled}
            value={o.date}
            onChange={(e) => patch(i, { date: e.target.value })}
          />
          <Select
            aria-label="Meal"
            disabled={disabled}
            value={o.period ?? ""}
            onChange={(e) => {
              const period = (e.target.value || null) as MealPeriod | null;
              patch(i, period ? { period } : { period: null, is_cancelled: true, starts: null, ends: null });
            }}
          >
            <option value="">Whole day</option>
            {PERIODS.map((p) => (
              <option key={p} value={p}>
                {PERIOD_LABEL[p]}
              </option>
            ))}
          </Select>
          <label className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <input
              type="checkbox"
              disabled={disabled || o.period === null}
              checked={o.is_cancelled}
              onChange={(e) => {
                const period = o.period ?? "lunch";
                patch(
                  i,
                  e.target.checked
                    ? { is_cancelled: true, starts: null, ends: null }
                    : { is_cancelled: false, starts: DEFAULT_TIMES[period][0], ends: DEFAULT_TIMES[period][1] },
                );
              }}
            />
            Cancelled
          </label>
          {!o.is_cancelled ? (
            <>
              <TextInput
                type="time"
                aria-label="Override starts"
                disabled={disabled}
                value={o.starts ?? ""}
                onChange={(e) => patch(i, { starts: e.target.value })}
              />
              <span className="text-muted">–</span>
              <TextInput
                type="time"
                aria-label="Override ends"
                disabled={disabled}
                value={o.ends ?? ""}
                onChange={(e) => patch(i, { ends: e.target.value })}
              />
            </>
          ) : null}
          <TextInput
            aria-label="Reason"
            placeholder="Reason shown to students"
            maxLength={120}
            disabled={disabled}
            value={o.reason ?? ""}
            onChange={(e) => patch(i, { reason: e.target.value || null })}
          />
          {!disabled ? (
            <Button
              aria-label="Remove override"
              className="min-h-9 px-2.5"
              onClick={() => setDraft({ ...draft, overrides: draft.overrides.filter((_, j) => j !== i) })}
            >
              ×
            </Button>
          ) : null}
        </div>
      ))}
      {!disabled ? (
        <div>
          <Button
            onClick={() =>
              setDraft({
                ...draft,
                overrides: [
                  ...draft.overrides,
                  { date: today, period: "lunch", is_cancelled: false, starts: "12:00", ends: "13:30", reason: null },
                ],
              })
            }
          >
            + Override
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function ScheduleEditor({ set }: { set: MealScheduleSet }) {
  const saved = useMemo(() => fromSet(set), [set]);
  const [draft, setDraft] = useState(saved);
  const save = useSaveMealSchedules();
  useEffect(() => setDraft(saved), [saved]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  useUnsavedGuard(dirty);
  const disabled = !set.can_edit;
  const isCanteen = set.canteen_id !== null;
  const shownWeek = draft.ownWeek
    ? draft
    : { ...draft, weekly: set.campus_weekly.map((s) => ({ ...s, starts: hm(s.starts), ends: hm(s.ends) })) };
  return (
    <>
      {disabled ? <Banner>Only the campus admin can change the campus default. You can override it for your own canteen.</Banner> : null}
      {save.isError ? <Banner tone="error">{errorText(save.error)}</Banner> : null}
      <Panel
        title={`${set.canteen_name} · weekly meals`}
        aside={
          !disabled ? (
            <div className="flex items-center gap-2">
              {dirty ? <span className="text-xs font-semibold text-busy">Unsaved changes</span> : null}
              <Button disabled={!dirty || save.isPending} onClick={() => setDraft(saved)}>
                Reset
              </Button>
              <Button
                tone="primary"
                disabled={!dirty || save.isPending}
                onClick={() =>
                  save.mutate({ canteen_id: set.canteen_id, weekly: draft.ownWeek ? draft.weekly : null, overrides: draft.overrides })
                }
              >
                {save.isPending ? "Saving…" : "Save schedule"}
              </Button>
            </div>
          ) : null
        }
      >
        {isCanteen ? (
          <fieldset className="m-0 flex flex-wrap gap-4 border-0 p-0 text-sm font-semibold" disabled={disabled}>
            <legend className="sr-only">Weekly schedule source</legend>
            <label className="inline-flex items-center gap-1.5">
              <input type="radio" checked={!draft.ownWeek} onChange={() => setDraft({ ...draft, ownWeek: false })} />
              Follow the campus default
            </label>
            <label className="inline-flex items-center gap-1.5">
              <input
                type="radio"
                checked={draft.ownWeek}
                onChange={() => setDraft({ ...draft, ownWeek: true, weekly: draft.weekly.length ? draft.weekly : shownWeek.weekly })}
              />
              Own weekly schedule
            </label>
          </fieldset>
        ) : null}
        <p className="m-0 text-xs text-muted">Times are Asia/Colombo. Students see the countdown from the server clock.</p>
        <div className={cx(isCanteen && !draft.ownWeek && "opacity-70")}>
          <WeekGrid draft={shownWeek} setDraft={setDraft} disabled={disabled || (isCanteen && !draft.ownWeek)} />
        </div>
      </Panel>
      <Panel title="Date overrides">
        <p className="m-0 text-xs text-muted">
          Holidays, exam days and special hours.{" "}
          {isCanteen
            ? "These apply to this canteen on top of its weekly meals."
            : "These apply to every canteen that follows the campus default."}
        </p>
        <OverrideList draft={draft} setDraft={setDraft} disabled={disabled} today={campusDate(set.server_time)} />
      </Panel>
    </>
  );
}

export function SchedulesScreen() {
  const session = useStaffSession();
  const canteens = useCanteens();
  const user = session.status === "signed_in" ? session.user : null;
  const options = (canteens.data?.items ?? []).filter((c) => user?.role === "campus_admin" || user?.canteen_ids.includes(c.id));
  const [owner, setOwner] = useState<string | null>(user?.role === "campus_admin" ? null : (user?.canteen_ids[0] ?? null));
  const schedules = useMealSchedules(owner);
  return (
    <Page title="Meal schedules" sub="Campus default with per-canteen overrides.">
      {apiMode() === "sample" ? (
        <Banner>Editing schedules needs the real API. Start it with pnpm stack:up, then pnpm dev:console:api.</Banner>
      ) : null}
      <nav aria-label="Schedule owner" className="flex flex-wrap gap-2">
        {[{ id: null as string | null, name: "Campus default" }, ...options].map((o) => (
          <button
            key={o.id ?? "campus"}
            type="button"
            aria-current={o.id === owner ? "page" : undefined}
            onClick={() => setOwner(o.id)}
            className={cx(
              "min-h-10 rounded-[10px] border px-3 text-sm font-semibold",
              o.id === owner ? "border-brand bg-brand text-white" : "border-line bg-card text-ink hover:bg-page",
            )}
          >
            {o.name}
          </button>
        ))}
      </nav>
      {schedules.isError && apiMode() === "api" ? <Banner tone="error">{errorText(schedules.error)}</Banner> : null}
      {schedules.data ? <ScheduleEditor key={owner ?? "campus"} set={schedules.data} /> : null}
    </Page>
  );
}
