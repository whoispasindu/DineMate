import { apiMode, useConsoleOverview, useZoneHistory, type HistoryBucket, type ZoneHistory } from "@dinemate/api-client";
import { cx, formatClock24, SampleBadge } from "@dinemate/ui";
import { useState } from "react";
import { Banner, errorText, Field, Page, Panel, Select } from "../kit";

const RANGES: { hours: number; bucket: HistoryBucket; label: string }[] = [
  { hours: 4, bucket: "5m", label: "Last 4 hours · 5 min" },
  { hours: 24, bucket: "15m", label: "Last 24 hours · 15 min" },
  { hours: 168, bucket: "1h", label: "Last 7 days · 1 hour" },
];

const dayFormat = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Colombo", weekday: "short" });

function label(t: string, hours: number): string {
  return hours > 24 ? `${dayFormat.format(Date.parse(t))} ${formatClock24(t)}` : formatClock24(t);
}

function HistoryChart({ history, hours }: { history: ZoneHistory; hours: number }) {
  const { points, capacity } = history;
  if (points.length === 0) return <Banner>No readings in this range.</Banner>;
  const every = Math.max(1, Math.ceil(points.length / 8));
  return (
    <>
      <div aria-hidden="true" className="flex h-48 items-end gap-px border-b border-line pb-px">
        {points.map((p) => {
          const pct = (v: number) => Math.min(100, (v / capacity) * 100);
          return (
            <div
              key={p.t}
              className="relative flex h-full min-w-0 flex-1 items-end"
              title={`${label(p.t, hours)} · ~${Math.round(p.mean)} of ${capacity}`}
            >
              <div
                className="absolute inset-x-0 rounded-sm bg-forecast-soft"
                style={{ bottom: `${pct(p.low)}%`, height: `${Math.max(1, pct(p.high) - pct(p.low))}%` }}
              />
              <div
                className={cx("relative w-full rounded-t-sm", pct(p.mean) >= 80 ? "bg-crowd-mark" : "bg-brand")}
                style={{ height: `${Math.max(1, pct(p.mean))}%` }}
              />
            </div>
          );
        })}
      </div>
      <div aria-hidden="true" className="flex justify-between text-[11px] text-muted">
        {points
          .filter((_, i) => i % every === 0)
          .map((p) => (
            <span key={p.t}>{label(p.t, hours)}</span>
          ))}
      </div>
      <table className="sr-only">
        <caption>Seats in use for {history.zone_name}, estimate and 80% range</caption>
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">About</th>
            <th scope="col">Range</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.t}>
              <td>{label(p.t, hours)}</td>
              <td>{Math.round(p.mean)}</td>
              <td>
                {p.low}–{p.high}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex flex-wrap gap-4 text-xs text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-brand" /> Estimated seats in use
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-forecast-soft" /> Range (low–high)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-crowd-mark" /> 80% or more
        </span>
      </div>
    </>
  );
}

export function OccupancyScreen() {
  const overview = useConsoleOverview();
  const zones = overview.data?.zones ?? [];
  const [zoneId, setZoneId] = useState<string | undefined>();
  const [rangeIndex, setRangeIndex] = useState(0);
  const range = RANGES[rangeIndex] ?? RANGES[0];
  const selected = zoneId ?? zones[0]?.zone_id;
  const history = useZoneHistory(apiMode() === "api" ? selected : undefined, range?.hours ?? 4, range?.bucket ?? "5m");
  return (
    <Page
      title="Occupancy"
      sample={overview.data?.is_sample}
      sub="Seat estimates over time. Seating occupancy only, not building occupancy."
    >
      {apiMode() === "sample" ? <Banner>History needs the real API. Start it with pnpm stack:up, then pnpm dev:console:api.</Banner> : null}
      <div className="flex flex-wrap gap-3">
        <Field label="Zone">
          <Select value={selected ?? ""} onChange={(e) => setZoneId(e.target.value)}>
            {zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.canteen_name} · {z.name} ({z.capacity} seats)
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Range">
          <Select value={rangeIndex} onChange={(e) => setRangeIndex(Number(e.target.value))}>
            {RANGES.map((r, i) => (
              <option key={r.hours} value={i}>
                {r.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {history.isError ? <Banner tone="error">{errorText(history.error)}</Banner> : null}
      {history.data && range ? (
        <Panel
          title={`${history.data.zone_name} · ${history.data.capacity} seats`}
          aside={history.data.is_simulated ? <SampleBadge>INCLUDES SIMULATED DATA</SampleBadge> : null}
        >
          <HistoryChart history={history.data} hours={range.hours} />
        </Panel>
      ) : null}
    </Page>
  );
}
