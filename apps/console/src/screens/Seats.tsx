import {
  apiMode,
  useCanteens,
  useCanteenSeats,
  useConsoleOverview,
  useServerNow,
  useStayTimes,
  useZoneSeatMap,
  type SeatStateName,
  type ZoneSeats,
} from "@dinemate/api-client";
import { cx, SampleBadge } from "@dinemate/ui";
import { useMemo, useState } from "react";
import { Banner, errorText, Field, Page, Panel, Select } from "../kit";

const HELD_LIMIT_MIN = 15;

const SEAT_STYLE: Record<SeatStateName, { fill: string; label: string; swatch: string }> = {
  free: { fill: "var(--color-ok-mark)", label: "Free", swatch: "bg-ok-mark" },
  occupied: { fill: "var(--color-crowd-mark)", label: "Taken", swatch: "bg-crowd-mark" },
  held: { fill: "var(--color-busy-mark)", label: "Held by bags", swatch: "bg-busy-mark" },
  unknown: { fill: "var(--color-faint)", label: "Hidden", swatch: "bg-faint" },
};

function count(value: number | null): string {
  return value === null ? "—" : String(value);
}

function minutesSince(since: string | null, now: number): number | null {
  return since ? Math.max(0, Math.round((now - Date.parse(since)) / 60_000)) : null;
}

function ZoneRow({ zone }: { zone: ZoneSeats }) {
  return (
    <tr className={cx("border-b border-line-soft", zone.freshness === "stale" && "opacity-70")}>
      <td className="py-2.5 pr-2 font-bold">{zone.name}</td>
      <td className="py-2.5 text-right">{count(zone.free)}</td>
      <td className="py-2.5 text-right">{count(zone.occupied)}</td>
      <td className="py-2.5 text-right">{count(zone.held)}</td>
      <td className="py-2.5 text-right">{count(zone.unknown)}</td>
      <td className="py-2.5 text-right">{count(zone.free_soon)}</td>
      <td className="py-2.5 pl-3">
        {zone.freshness === "unavailable" ? (
          <span className="text-muted">No live data</span>
        ) : zone.crowded ? (
          <span className="font-bold text-crowd">Crowded · {count(zone.standing)} standing</span>
        ) : (
          <span className="text-ink-2">{zone.freshness === "stale" ? "May be out of date" : "OK"}</span>
        )}
      </td>
    </tr>
  );
}

function SeatMap({ zoneId, now }: { zoneId: string; now: number }) {
  const map = useZoneSeatMap(zoneId);
  if (!map.data || map.data.seats.length === 0) return null;
  const longHeld = map.data.seats
    .filter((s) => s.state === "held")
    .map((s) => ({ seat: s, minutes: minutesSince(s.since, now) }))
    .filter((h): h is { seat: (typeof h)["seat"]; minutes: number } => h.minutes !== null && h.minutes >= HELD_LIMIT_MIN);
  return (
    <Panel title={`Seat map · ${map.data.name}`} aside={<span className="text-xs text-muted">{map.data.seats.length} seats</span>}>
      <svg
        viewBox="0 0 160 90"
        role="img"
        aria-label={`Seat map for ${map.data.name}`}
        className="w-full max-w-[640px] rounded-xl border border-line bg-surface-soft"
      >
        {map.data.seats.map((s) => (
          <circle key={s.seat_id} cx={s.x * 160} cy={s.y * 90} r={2.6} fill={SEAT_STYLE[s.state].fill}>
            <title>
              {s.seat_id}: {SEAT_STYLE[s.state].label}
              {s.free_soon ? " (plates left, free soon)" : ""}
            </title>
          </circle>
        ))}
      </svg>
      <div className="flex flex-wrap gap-4 text-xs text-ink-2">
        {(Object.keys(SEAT_STYLE) as SeatStateName[]).map((state) => (
          <span key={state} className="inline-flex items-center gap-1.5">
            <span className={cx("h-3 w-3 rounded-full", SEAT_STYLE[state].swatch)} /> {SEAT_STYLE[state].label}
          </span>
        ))}
      </div>
      {longHeld.length > 0 ? (
        <Banner>
          Held over {HELD_LIMIT_MIN} min: {longHeld.map((h) => `${h.seat.seat_id} (${h.minutes} min)`).join(", ")}
        </Banner>
      ) : null}
    </Panel>
  );
}

function StayPanel({ canteenId }: { canteenId: string }) {
  const stays = useStayTimes(canteenId);
  if (stays.isError) return <Banner tone="error">{errorText(stays.error)}</Banner>;
  if (!stays.data) return null;
  const s = stays.data;
  return (
    <Panel title="Stay times" aside={<SampleBadge>EXPERIMENTAL</SampleBadge>}>
      {s.sessions === 0 ? (
        <span className="text-sm text-muted">No finished seat visits in the last {s.days} days yet.</span>
      ) : (
        <div className="flex flex-col gap-3 text-sm">
          <div className="flex flex-wrap gap-6">
            <span>
              Typical stay <strong>~{s.median_minutes} min</strong> ({s.sessions} visits, last {s.days} days)
            </span>
            <span>
              Taken now <strong>{s.occupied_now}</strong>
              {s.likely_free_10min !== null ? (
                <>
                  {" "}
                  · about <strong>{s.likely_free_10min}</strong> likely to free up in 10 min
                </>
              ) : null}
            </span>
          </div>
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {s.hours.map((h) => (
              <li key={h.hour} className="rounded-lg bg-page px-2.5 py-1.5 text-xs">
                {String(h.hour).padStart(2, "0")}:00 · ~{h.median_minutes} min ({h.sessions})
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}

export function SeatsScreen() {
  const now = useServerNow();
  const overview = useConsoleOverview();
  const canteens = useCanteens();
  const mine = useMemo(() => {
    const names = new Set((overview.data?.zones ?? []).map((z) => z.canteen_name));
    return (canteens.data?.items ?? []).filter((c) => names.size === 0 || names.has(c.name));
  }, [overview.data, canteens.data]);
  const [picked, setPicked] = useState<string | undefined>();
  const canteenId = picked ?? mine[0]?.id;
  const seats = useCanteenSeats(canteenId);
  const live = apiMode() === "api";
  return (
    <Page
      title="Seats"
      sample={overview.data?.is_sample}
      sub="Each seat is free, taken, held by bags or hidden. Hidden and held seats are never shown to students as free."
    >
      <Field label="Canteen" className="max-w-[320px]">
        <Select value={canteenId ?? ""} onChange={(e) => setPicked(e.target.value)}>
          {mine.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </Field>
      {seats.isError ? <Banner tone="error">{errorText(seats.error)}</Banner> : null}
      <Panel title="Seats now">
        {seats.data && seats.data.zones.length > 0 ? (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 pr-2 font-semibold">Zone</th>
                <th className="py-2 text-right font-semibold">Free</th>
                <th className="py-2 text-right font-semibold">Taken</th>
                <th className="py-2 text-right font-semibold">Held</th>
                <th className="py-2 text-right font-semibold">Hidden</th>
                <th className="py-2 text-right font-semibold">Free soon</th>
                <th className="py-2 pl-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {seats.data.zones.map((z) => (
                <ZoneRow key={z.zone_id} zone={z} />
              ))}
            </tbody>
          </table>
        ) : (
          <span className="text-sm text-muted">No seat data for this canteen yet.</span>
        )}
      </Panel>
      {live ? (
        <>
          {(seats.data?.zones ?? []).map((z) => (
            <SeatMap key={z.zone_id} zoneId={z.zone_id} now={now} />
          ))}
          {canteenId ? <StayPanel canteenId={canteenId} /> : null}
        </>
      ) : (
        <Banner>Seat maps and stay times need the real API. Start it with pnpm stack:up, then pnpm dev:console:api.</Banner>
      )}
    </Page>
  );
}
