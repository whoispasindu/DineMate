import { useReport, type ReportRange, type VenueReport } from "@dinemate/api-client";
import { cx } from "@dinemate/ui";
import { useState } from "react";
import { Banner, errorText, Page, Panel, Skeleton } from "../kit";
import { useVenue } from "../venue";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const OPTIONS: { value: ReportRange; label: string }[] = [
  { value: "day", label: "Today" },
  { value: "week", label: "Last 7 days" },
];

function dayLabel(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  return `${WEEKDAYS[(date.getUTCDay() + 6) % 7]} ${date.getUTCDate()}`;
}

function Days({ data }: { data: VenueReport }) {
  const top = Math.max(1, ...data.days.map((d) => d.visits));
  const visits = data.days.reduce((s, d) => s + d.visits, 0);
  const guests = data.days.reduce((s, d) => s + d.guests, 0);
  return (
    <Panel
      title="Visits"
      aside={
        <span className="text-[13px] text-muted">
          {visits} visits · ~{guests} guests
        </span>
      }
      className="flex-[1_1_420px]"
    >
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-muted">
            <th className="pb-2 font-semibold">Day</th>
            <th className="pb-2 font-semibold">Visits</th>
            <th className="pb-2 text-right font-semibold">Guests</th>
            <th className="pb-2 text-right font-semibold">Avg stay</th>
          </tr>
        </thead>
        <tbody>
          {data.days.map((d) => (
            <tr key={d.day} className="border-t border-line-soft">
              <td className="py-2.5 pr-2 font-semibold">{dayLabel(d.day)}</td>
              <td className="py-2.5 pr-3">
                <span className="flex items-center gap-2.5">
                  <span aria-hidden="true" className="h-2.5 w-[140px] overflow-hidden rounded-full bg-track">
                    <span className="block h-full rounded-full bg-brand" style={{ width: `${(d.visits / top) * 100}%` }} />
                  </span>
                  <span className="font-bold">{d.visits}</span>
                </span>
              </td>
              <td className="py-2.5 text-right">{d.guests}</td>
              <td className="py-2.5 text-right">{d.avg_stay_min !== null ? `${d.avg_stay_min} min` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function Heat({ data }: { data: VenueReport }) {
  const cells = new Map(data.heat.map((c) => [`${c.weekday}-${c.hour}`, c.visits]));
  const hours = Array.from(new Set(data.heat.map((c) => c.hour))).sort((a, b) => a - b);
  const top = Math.max(1, ...data.heat.map((c) => c.visits));
  const busiest = [...data.heat].sort((a, b) => b.visits - a.visits).slice(0, 3);
  return (
    <Panel
      title="Busiest hours"
      aside={<span className="text-[13px] text-muted">Visits started, last {data.heat_days} days</span>}
      className="flex-[1.4_1_520px]"
    >
      {hours.length === 0 ? (
        <p className="m-0 text-sm text-muted">No visits recorded yet.</p>
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Visits by weekday and hour">
          <table className="border-collapse text-xs">
            <thead>
              <tr>
                <th className="sr-only">Day</th>
                {hours.map((h) => (
                  <th key={h} scope="col" className="px-0.5 pb-1.5 font-semibold text-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {WEEKDAYS.map((name, wd) => (
                <tr key={name}>
                  <th scope="row" className="pr-2 text-left font-semibold text-muted">
                    {name}
                  </th>
                  {hours.map((h) => {
                    const v = cells.get(`${wd}-${h}`) ?? 0;
                    return (
                      <td key={h} className="p-0.5">
                        <span
                          title={`${name} ${h}:00 · ${v} visits`}
                          className="block h-7 w-8 rounded-[5px]"
                          style={{
                            background:
                              v === 0
                                ? "var(--color-track)"
                                : `color-mix(in srgb, var(--color-purple) ${Math.round(15 + (v / top) * 85)}%, white)`,
                          }}
                        >
                          <span className="sr-only">
                            {name} {h}:00, {v} visits
                          </span>
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {busiest.length > 0 ? (
        <p className="m-0 text-sm text-ink-2">
          Busiest: {busiest.map((c) => `${WEEKDAYS[c.weekday]} ${c.hour}:00`).join(", ")}. Plan staff and stock for these slots.
        </p>
      ) : null}
    </Panel>
  );
}

export function ReportsScreen() {
  const { venue } = useVenue();
  const [range, setRange] = useState<ReportRange>("week");
  const report = useReport(venue?.id, range);
  const data = report.data;
  return (
    <Page
      title="Reports"
      sub="Visits, guests and busy hours"
      sample={data?.is_sample}
      actions={
        <div role="group" aria-label="Report range" className="flex gap-1 rounded-[12px] bg-chip p-1">
          {OPTIONS.map((o) => (
            <button
              key={o.value}
              type="button"
              aria-pressed={range === o.value}
              onClick={() => setRange(o.value)}
              className={cx(
                "min-h-9 rounded-[9px] border-0 px-3.5 text-[13px]",
                range === o.value ? "bg-brand font-bold text-on-dark" : "bg-transparent font-semibold text-muted hover:text-ink",
              )}
            >
              {o.label}
            </button>
          ))}
        </div>
      }
    >
      {report.isError ? <Banner tone="error">{errorText(report.error)}</Banner> : null}
      {!data ? (
        <Skeleton className="h-[360px]" />
      ) : (
        <div className="flex flex-wrap items-start gap-4">
          <Days data={data} />
          <Heat data={data} />
        </div>
      )}
    </Page>
  );
}
