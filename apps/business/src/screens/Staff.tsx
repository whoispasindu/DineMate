import { useServerNow, useStaffReport, type StaffReport, type StaffUser } from "@dinemate/api-client";
import { cx, formatClock, formatRange } from "@dinemate/ui";
import { Link } from "react-router";
import { Banner, errorText, Kpi, Page, Panel, Skeleton } from "../kit";
import { AreaBar, AreaLegend, hoursMinutes, MethodChip, OwnerOnly, totalMinutes } from "../staff";
import { useVenue } from "../venue";

const MIN = 60_000;

function Coverage({ data, now }: { data: StaffReport; now: number }) {
  const { coverage } = data;
  const end = Math.min(now, Date.parse(data.server_time));
  const start = end - coverage.open_min * MIN;
  const span = Math.max(1, end - start);
  const at = (value: string) => `${Math.min(100, Math.max(0, ((Date.parse(value) - start) / span) * 100))}%`;
  const width = (a: string, b: string) => `${Math.max(0.6, ((Date.parse(b) - Date.parse(a)) / span) * 100)}%`;
  return (
    <Panel
      title="Counter coverage"
      aside={<span className="text-[13px] text-muted">Someone at the counter while open</span>}
      className="flex-[1.5_1_520px]"
    >
      {coverage.open_min === 0 ? <p className="m-0 text-sm text-muted">Not open yet today.</p> : null}
      {coverage.open_min > 0 ? (
        <>
          <div className="relative h-9 overflow-hidden rounded-[10px] bg-ok-bg" aria-hidden="true">
            {coverage.gaps.map((g) => (
              <span
                key={g.start}
                className="absolute inset-y-0 bg-crowd-mark"
                style={{ left: at(g.start), width: width(g.start, g.end) }}
              />
            ))}
            {data.queue_alerts.map((q) => (
              <span
                key={q.start}
                className="absolute bottom-0 h-2 rounded-t bg-busy-mark"
                style={{ left: at(q.start), width: width(q.start, q.end) }}
              />
            ))}
          </div>
          <div className="flex justify-between text-xs text-muted">
            <span>{formatClock(start)}</span>
            <span>now</span>
          </div>
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-sm">
            {coverage.gaps.map((g) => (
              <li key={g.start} className="flex items-center gap-2.5">
                <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-crowd-mark" />
                <span className="font-semibold">{formatRange(g.start, g.end)}</span>
                <span className="text-muted">nobody at the counter for {g.minutes} min</span>
              </li>
            ))}
            {data.queue_alerts.map((q) => (
              <li key={q.start} className="flex items-center gap-2.5">
                <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-busy-mark" />
                <span className="font-semibold">{formatRange(q.start, q.end)}</span>
                <span className="text-muted">queue of up to ~{q.peak}</span>
              </li>
            ))}
            {coverage.gaps.length + data.queue_alerts.length === 0 ? (
              <li className="text-muted">No gaps and no long queues so far today.</li>
            ) : null}
          </ul>
        </>
      ) : null}
    </Panel>
  );
}

function Workers({ data }: { data: StaffReport }) {
  const scale = Math.max(60, ...data.workers.map((w) => totalMinutes(w.minutes)));
  return (
    <Panel title="Who worked where" aside={<AreaLegend />}>
      {data.workers.length === 0 ? <p className="m-0 text-sm text-muted">No consented staff were seen today.</p> : null}
      <ul className="m-0 flex list-none flex-col p-0">
        {data.workers.map((w, i) => (
          <li key={w.staff_id} className={cx("flex flex-wrap items-center gap-x-4 gap-y-2 py-3", i > 0 && "border-t border-line-soft")}>
            <span className="flex w-[230px] flex-col">
              <span className="flex items-center gap-2 text-[15px] font-bold">
                {w.display_name}
                <MethodChip method={w.method} />
              </span>
              <span className="text-[13px] text-muted">
                {w.role_label || "Staff"}
                {w.first_seen && w.last_seen ? ` · ${formatRange(w.first_seen, w.last_seen)}` : " · not seen today"}
              </span>
            </span>
            <span className="flex min-w-[200px] flex-[1_1_220px] items-center gap-3">
              <AreaBar minutes={w.minutes} scale={scale} />
              <span className="w-[86px] text-right text-sm font-bold">{hoursMinutes(totalMinutes(w.minutes))}</span>
            </span>
            <span className="sr-only">
              Counter {w.minutes.counter} min, kitchen {w.minutes.kitchen} min, floor {w.minutes.floor} min.
            </span>
            <span className="w-[110px] text-sm">
              {w.orders > 0 ? (
                <>
                  <span className="font-bold">{w.total_items}</span> <span className="text-muted">items served</span>
                </>
              ) : (
                <span className="text-muted">No till orders</span>
              )}
            </span>
            <Link
              to={`/staff/${w.staff_id}/sheet`}
              className="text-sm font-bold text-purple-ink underline-offset-2 hover:underline"
              aria-label={`Print sheet for ${w.display_name}`}
            >
              Print sheet
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Items({ data }: { data: StaffReport }) {
  const sellers = data.workers.filter((w) => w.total_items > 0);
  return (
    <Panel title="Items served" aside={<span className="text-[13px] text-muted">From the till, by cashier code</span>}>
      {sellers.length === 0 ? (
        <p className="m-0 text-sm text-muted">No till orders matched to staff today. Import a till file in Sales.</p>
      ) : null}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {sellers.map((w) => (
          <li key={w.staff_id} className="flex flex-col gap-1">
            <span className="text-sm font-bold">
              {w.display_name} <span className="font-normal text-muted">· {w.orders} orders</span>
            </span>
            <span className="text-[13px] text-ink-2">{w.items.map((i) => `${i.name} ${i.qty}`).join(" · ")}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function StaffScreen({ user }: { user: StaffUser }) {
  const { venue } = useVenue();
  const owner = user.role === "owner";
  const report = useStaffReport(venue?.id, undefined, owner);
  const now = useServerNow(30_000);
  const data = report.data;
  if (!owner) {
    return (
      <Page title="Staff" sub="Owner only">
        <OwnerOnly what="The staff report" />
      </Page>
    );
  }
  const items = data?.workers.reduce((sum, w) => sum + w.total_items, 0) ?? 0;
  const longest = data?.coverage.gaps.reduce((best, g) => Math.max(best, g.minutes), 0) ?? 0;
  return (
    <Page title="Staff" sub="Today · consented staff only" sample={data?.is_sample}>
      {report.isError ? <Banner tone="error">{errorText(report.error)}</Banner> : null}
      {!data ? (
        <div role="status" aria-label="Loading staff report" className="flex flex-col gap-4">
          <Skeleton className="h-[118px]" />
          <Skeleton className="h-[300px]" />
        </div>
      ) : (
        <>
          <section aria-label="Key figures" className="flex flex-wrap gap-4">
            <Kpi
              hero
              label="Counter covered"
              value={data.coverage.share !== null ? `${Math.round(data.coverage.share * 100)}%` : "—"}
              note={`${hoursMinutes(data.coverage.covered_min)} of ${hoursMinutes(data.coverage.open_min)} open`}
            />
            <Kpi
              label="Counter gaps"
              value={data.coverage.gaps.length}
              note={longest > 0 ? `Longest ${longest} min` : "None today"}
              tone={data.coverage.gaps.length > 0 ? "alert" : "ok"}
            />
            <Kpi
              label="Long queues"
              value={data.queue_alerts.length}
              note="Over 5 people for a minute or more"
              tone={data.queue_alerts.length > 0 ? "alert" : "ok"}
            />
            <Kpi label="Items served" value={items} note={`By ${data.workers.filter((w) => w.total_items > 0).length} cashiers`} />
          </section>
          <div className="flex flex-wrap items-start gap-4">
            <Coverage data={data} now={now} />
            <div className="flex min-w-[300px] flex-[1_1_340px] flex-col gap-4">
              <Items data={data} />
            </div>
          </div>
          <Workers data={data} />
          <p className="m-0 text-xs text-muted">
            Only staff who signed consent are recognised, and only inside work areas. Customers are never identified. Every view of this
            page is recorded in Privacy &amp; consent.
          </p>
        </>
      )}
    </Page>
  );
}
