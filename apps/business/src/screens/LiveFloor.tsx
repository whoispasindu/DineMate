import { useFloor, useMarkCleared, useServerNow, type FloorTable, type VenueFloor } from "@dinemate/api-client";
import { cx, formatAgo, formatDayStamp, Icon, LiveLine, SampleBadge } from "@dinemate/ui";
import { Banner, Button, errorText, Kpi, Page, Panel, Skeleton } from "../kit";
import { estimateText, isSoon, LEGEND, minutesSince, tableLook, tableSummary, urgency } from "../tables";
import { useIsWide, useVenue } from "../venue";

function liveText(floor: VenueFloor, now: number): string {
  return floor.updated_at ? `Live · ${formatAgo(floor.updated_at, now)}` : "Waiting for the camera";
}

function FloorMap({ floor, now }: { floor: VenueFloor; now: number }) {
  return (
    <div className="relative w-full overflow-hidden rounded-[18px] border border-line bg-page" style={{ aspectRatio: "4 / 3" }}>
      <ul aria-label="Floor map" className="m-0 list-none p-0">
        {floor.tables.map((t) => {
          const look = tableLook(t, now);
          return (
            <li
              key={t.id}
              aria-label={tableSummary(t, now)}
              className={cx(
                "absolute flex flex-col items-center justify-center gap-0.5 text-center leading-tight",
                t.shape === "round" ? "rounded-full" : "rounded-[14px]",
                look.className,
              )}
              style={{ left: `${t.x * 100}%`, top: `${t.y * 100}%`, width: `${t.w * 100}%`, height: `${t.h * 100}%` }}
            >
              <b aria-hidden="true" className="font-display text-[15px] font-extrabold">
                {t.name}
              </b>
              <span aria-hidden="true" className="text-xs font-semibold">
                {look.title}
              </span>
              <span aria-hidden="true" className="hidden text-xs font-semibold opacity-90 lg:block">
                {look.detail}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function SoonList({ tables }: { tables: FloorTable[] }) {
  const soon = tables
    .filter((t) => t.state === "occupied" && t.estimate)
    .sort((a, b) => (a.estimate?.high_min ?? 0) - (b.estimate?.high_min ?? 0))
    .slice(0, 4);
  return (
    <Panel title="Freeing up soon" aside={<span className="text-xs font-semibold text-muted">Estimate · experimental</span>}>
      {soon.length === 0 ? <p className="m-0 text-sm text-muted">No seated tables with an estimate yet.</p> : null}
      <ul className="m-0 flex list-none flex-col p-0">
        {soon.map((t, i) => (
          <li key={t.id} className={cx("flex items-center justify-between gap-3 py-2.5", i > 0 && "border-t border-line-soft")}>
            <span className="flex flex-col">
              <span className="text-[15px] font-bold">
                {t.name} <span className="font-medium text-muted">· {t.zone_name}</span>
              </span>
              <span className="text-[13px] text-muted">
                {t.party_size} guests · {t.seated_min} min
              </span>
            </span>
            <span className={cx("text-sm font-bold", isSoon(t) ? "text-purple-ink" : "text-ink-2")}>{estimateText(t)}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Attention({ floor, now, venueId }: { floor: VenueFloor; now: number; venueId: string }) {
  const clear = useMarkCleared(venueId);
  const toClear = floor.tables.filter((t) => t.state === "needs_clearing");
  const held = floor.tables.filter((t) => t.state === "held" && (minutesSince(t.since, now) ?? 0) >= 5);
  const blind = floor.tables.filter((t) => t.state === "unknown");
  const empty = toClear.length + held.length + blind.length === 0;
  return (
    <Panel title="Needs attention">
      {clear.isError ? <Banner tone="error">{errorText(clear.error)}</Banner> : null}
      {empty ? <p className="m-0 text-sm text-muted">Nothing needs you right now.</p> : null}
      {toClear.map((t) => (
        <div key={t.id} className="flex items-center justify-between gap-3 rounded-[14px] bg-crowd-bg px-3.5 py-3">
          <span className="flex flex-col">
            <span className="text-[15px] font-bold text-crowd">{t.name} needs clearing</span>
            <span className="text-[13px] text-crowd">Guests left {minutesSince(t.since, now)} min ago</span>
          </span>
          <Button tone="primary" className="min-h-9" disabled={clear.isPending} onClick={() => clear.mutate(t.id)}>
            Mark cleared<span className="sr-only"> {t.name}</span>
          </Button>
        </div>
      ))}
      {held.map((t) => (
        <div key={t.id} className="flex flex-col rounded-[14px] bg-busy-bg px-3.5 py-3 text-busy">
          <span className="text-[15px] font-bold">
            {t.name} held by a bag for {minutesSince(t.since, now)} min
          </span>
          <span className="text-[13px]">Nobody seated</span>
        </div>
      ))}
      {blind.map((t) => (
        <div key={t.id} className="flex flex-col rounded-[14px] bg-chip px-3.5 py-3 text-neutral-ink">
          <span className="text-[15px] font-bold">{t.name}: camera can't see it</span>
          <span className="text-[13px]">No state shown until the camera reports again</span>
        </div>
      ))}
    </Panel>
  );
}

function Totals({ floor }: { floor: VenueFloor }) {
  const soon = floor.tables.filter(isSoon).length;
  const t = floor.totals;
  return (
    <section aria-label="Key figures" className="flex flex-wrap gap-4">
      <Kpi
        hero
        label="Tables free now"
        value={
          <>
            {t.free} <span className="font-sans text-xl font-medium tracking-normal text-on-dark-faint">of {t.tables}</span>
          </>
        }
        note={soon > 0 ? `${soon} more likely free in ${10} min` : "None expected to free up in 10 min"}
      />
      <Kpi label="Guests seated" value={`~${t.guests_seated}`} note={`${t.visits_today} visits so far today`} />
      <Kpi
        label="Average stay today"
        value={t.avg_stay_today_min !== null ? `${t.avg_stay_today_min} min` : "—"}
        note="Finished visits only"
      />
      <Kpi label="Turns today" value={t.turns_today.toFixed(1)} note="Visits per table" tone="ok" />
    </section>
  );
}

function PhoneFloor({ floor, now, venueId }: { floor: VenueFloor; now: number; venueId: string }) {
  const clear = useMarkCleared(venueId);
  const sorted = [...floor.tables].sort((a, b) => urgency(a) - urgency(b));
  const soon = floor.tables.filter(isSoon).length;
  return (
    <main id="main" className="flex flex-col gap-4 px-4 pb-28 pt-3">
      <div className="flex items-center justify-between">
        <h1 className="m-0 font-display text-[32px] font-extrabold tracking-[-0.04em]">Live floor</h1>
        <LiveLine text={floor.updated_at ? "Live" : "Waiting"} freshness={floor.updated_at ? "live" : "stale"} />
      </div>
      <section aria-label="Tables free" className="slab flex items-end justify-between rounded-[22px] bg-brand px-5 py-[18px] text-on-dark">
        <span className="flex flex-col">
          <span className="text-[13px] font-semibold text-on-dark-faint">Tables free</span>
          <span className="font-display text-[52px] font-extrabold leading-[0.9] tracking-[-0.05em]">
            {floor.totals.free}
            <span className="font-sans text-xl font-medium tracking-normal text-on-dark-faint"> of {floor.totals.tables}</span>
          </span>
        </span>
        <span className="text-right text-[13px] leading-normal text-on-dark-faint">
          {soon} more in ~10 min
          <br />
          {floor.totals.guests_seated} guests seated
        </span>
      </section>
      {floor.is_sample ? <SampleBadge className="self-start" /> : null}
      <div className="flex items-baseline justify-between">
        <h2 className="m-0 text-[22px] font-semibold">Needs you</h2>
        <span className="text-[13px] text-muted">by urgency</span>
      </div>
      <ul className="m-0 flex list-none flex-col p-0">
        {sorted.map((t, i) => {
          const look = tableLook(t, now);
          return (
            <li key={t.id} className={cx("flex items-center gap-3.5 py-3", i > 0 && "border-t border-line")}>
              <span
                aria-hidden="true"
                className={cx(
                  "flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-[14px] font-display text-[15px] font-extrabold",
                  look.className,
                )}
              >
                {t.name}
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-[15px] font-bold">
                  <span className="sr-only">{t.name}: </span>
                  {look.word}
                </span>
                <span className="text-[13px] text-muted">
                  {t.state === "occupied" ? `${t.party_size} guests · ${t.seated_min} min` : `${t.seats} seats · ${look.detail}`}
                </span>
              </span>
              {t.state === "needs_clearing" ? (
                <Button tone="primary" className="min-h-9 px-3" disabled={clear.isPending} onClick={() => clear.mutate(t.id)}>
                  Cleared<span className="sr-only"> {t.name}</span>
                </Button>
              ) : null}
            </li>
          );
        })}
      </ul>
    </main>
  );
}

export function LiveFloorScreen() {
  const { venue, loading } = useVenue();
  const floor = useFloor(venue?.id);
  const now = useServerNow(1000);
  const wide = useIsWide();
  const data = floor.data;
  if (!loading && !venue) {
    return (
      <Page title="Live floor">
        <Banner>No venues are set up for this account yet.</Banner>
      </Page>
    );
  }
  if (!data || !venue) {
    return (
      <Page title="Live floor">
        {floor.isError ? <Banner tone="error">{errorText(floor.error)}</Banner> : null}
        <div role="status" aria-label="Loading the floor" className="flex flex-col gap-4">
          <Skeleton className="h-[118px]" />
          <Skeleton className="h-[420px]" />
        </div>
      </Page>
    );
  }
  if (!wide) return <PhoneFloor floor={data} now={now} venueId={venue.id} />;
  return (
    <Page
      title="Live floor"
      sub={formatDayStamp(now)}
      sample={data.is_sample}
      actions={<LiveLine text={liveText(data, now)} freshness={data.updated_at ? "live" : "stale"} />}
    >
      <Totals floor={data} />
      <div className="flex flex-wrap items-start gap-4">
        <Panel
          title={data.venue_name}
          className="min-w-[420px] flex-[1.7_1_560px]"
          aside={
            <ul aria-label="Legend" className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-[13px] font-semibold text-muted">
              {LEGEND.map((l) => (
                <li key={l.key} className="inline-flex items-center gap-2">
                  <span className={cx("h-3.5 w-[18px] rounded-[5px]", l.className)} />
                  {l.label}
                </li>
              ))}
            </ul>
          }
        >
          <FloorMap floor={data} now={now} />
          <p className="m-0 flex items-start gap-2 text-xs text-muted">
            <Icon name="lock" size={14} className="mt-px shrink-0" />
            Video never leaves the café and is never stored. Only table states and times are kept, with no customer identities.
          </p>
        </Panel>
        <div className="flex min-w-[300px] flex-[1_1_320px] flex-col gap-4">
          <SoonList tables={data.tables} />
          <Attention floor={data} now={now} venueId={venue.id} />
        </div>
      </div>
    </Page>
  );
}
