import { useCustomers, type CustomerDay } from "@dinemate/api-client";
import { cx } from "@dinemate/ui";
import { Banner, errorText, Kpi, Page, Panel, Skeleton } from "../kit";
import { useVenue } from "../venue";

function hourLabel(hour: number): string {
  if (hour === 12) return "12p";
  return hour > 12 ? String(hour - 12) : String(hour);
}

function change(now: number, before: number): string {
  if (before === 0) return "No visits by this time last week";
  const pct = Math.round(((now - before) / before) * 100);
  return `${pct >= 0 ? "+" : ""}${pct}% vs this time last week`;
}

function VisitsByHour({ data }: { data: CustomerDay }) {
  const active = data.by_hour.filter((h) => h.visits > 0);
  const first = active[0]?.hour ?? 7;
  const last = active.at(-1)?.hour ?? 20;
  const hours = data.by_hour.filter((h) => h.hour >= first && h.hour <= last);
  const top = Math.max(1, ...hours.map((h) => h.visits));
  const peak = hours.reduce((best, h) => (h.visits > best.visits ? h : best), hours[0] ?? { hour: 0, visits: 0 });
  return (
    <Panel
      title="Visits by hour"
      className="flex-[1.5_1_520px]"
      aside={
        peak.visits > 0 ? (
          <span className="text-[13px] text-muted">
            Peak {hourLabel(peak.hour)} · {peak.visits} visits
          </span>
        ) : null
      }
    >
      <ul className="m-0 flex h-[260px] list-none items-end gap-2 p-0">
        {hours.map((h) => (
          <li key={h.hour} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
            <span className="text-xs font-semibold text-muted">{h.visits}</span>
            <div
              aria-hidden="true"
              className={cx("w-full rounded-t-md rounded-b-sm", h.hour === peak.hour ? "bg-purple" : "bg-brand")}
              style={{ height: `${Math.max(3, (h.visits / top) * 200)}px` }}
            />
            <span className="text-xs text-muted">{hourLabel(h.hour)}</span>
            <span className="sr-only">
              {h.hour}:00, {h.visits} visits
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function StayByTable({ data }: { data: CustomerDay }) {
  const rows = [...data.by_table].sort((a, b) => (b.avg_stay_min ?? 0) - (a.avg_stay_min ?? 0));
  const top = Math.max(30, ...rows.map((r) => r.avg_stay_min ?? 0));
  return (
    <Panel title="Stay by table" aside={<span className="text-[13px] text-muted">Average · turns</span>}>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {rows.map((r) => (
          <li key={r.table_id} className="flex items-center gap-3 py-1.5">
            <span className="w-[92px] shrink-0 text-sm font-semibold">
              {r.name} · {r.seats} seats
            </span>
            <span aria-hidden="true" className="h-2.5 flex-1 overflow-hidden rounded-full bg-track">
              <span className="block h-full rounded-full bg-brand" style={{ width: `${((r.avg_stay_min ?? 0) / top) * 100}%` }} />
            </span>
            <span className="w-[56px] text-right text-sm font-bold">{r.avg_stay_min !== null ? `${r.avg_stay_min} min` : "—"}</span>
            <span className="w-[58px] text-right text-[13px] text-muted">{r.turns} turns</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function CustomersScreen() {
  const { venue } = useVenue();
  const day = useCustomers(venue?.id);
  const data = day.data;
  return (
    <Page title="Customers" sub="Anonymous visits · today" sample={data?.is_sample}>
      {day.isError ? <Banner tone="error">{errorText(day.error)}</Banner> : null}
      {!data ? (
        <div role="status" aria-label="Loading customers" className="flex flex-col gap-4">
          <Skeleton className="h-[118px]" />
          <Skeleton className="h-[320px]" />
        </div>
      ) : (
        <>
          <section aria-label="Key figures" className="flex flex-wrap gap-4">
            <Kpi hero label="Visits today" value={data.visits} note={change(data.visits, data.visits_last_week)} />
            <Kpi
              label="Average stay"
              value={data.avg_stay_min !== null ? `${data.avg_stay_min} min` : "—"}
              note={data.median_stay_min !== null ? `Median ${data.median_stay_min} min` : "No finished visits yet"}
            />
            <Kpi label="Table turns" value={data.turns_per_table.toFixed(1)} note="Visits per table so far" />
            <Kpi label="Guests" value={`~${data.guests}`} note="Counted from seats taken" tone="ok" />
          </section>
          <div className="flex flex-wrap items-start gap-4">
            <VisitsByHour data={data} />
            <div className="flex min-w-[320px] flex-[1_1_360px] flex-col gap-4">
              <StayByTable data={data} />
              <Panel title="Stay after paying">
                <p className="m-0 text-sm text-muted">
                  Matching visits to till orders needs a live till connection. Till files already feed Sales and Staff.
                </p>
              </Panel>
            </div>
          </div>
          <p className="m-0 text-xs text-muted">
            Customers are never identified. A visit is a table, a start and end time, and how many seats were taken.
          </p>
        </>
      )}
    </Page>
  );
}
