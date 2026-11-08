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
import { ApproxNumber, cx, EmptyStrip, SampleBadge, SeatStrip, TableScene } from "@dinemate/ui";
import { useMemo, useState } from "react";
import { Banner, errorText, Field, Page, Panel, Select } from "../kit";

const HELD_LIMIT_MIN = 15;

const SEAT_STYLE: Record<SeatStateName, { fill: string; label: string; swatch: string }> = {
  free: { fill: "var(--color-ok-mark)", label: "Free", swatch: "bg-ok-mark" },
  occupied: { fill: "var(--color-brand)", label: "Taken", swatch: "bg-brand" },
  held: { fill: "var(--color-held)", label: "Held by bags", swatch: "bg-held" },
  unknown: { fill: "var(--color-hidden)", label: "Hidden", swatch: "bg-hidden" },
};

function count(value: number | null): string {
  return value === null ? "—" : String(value);
}

function minutesSince(since: string | null, now: number): number | null {
  return since ? Math.max(0, Math.round((now - Date.parse(since)) / 60_000)) : null;
}

function ZoneRow({ zone, first }: { zone: ZoneSeats; first: boolean }) {
  const live = zone.freshness !== "unavailable" && zone.occupied !== null;
  const word = !live ? "No live data" : zone.crowded ? "Crowded" : zone.freshness === "stale" ? "May be out of date" : "Seats available";
  const wordTone = !live ? "text-faint" : zone.crowded ? "text-crowd-mark" : zone.freshness === "stale" ? "text-busy" : "text-ok-mark";
  const note = !live
    ? "Camera offline, no numbers shown"
    : zone.crowded
      ? `${count(zone.standing)} people standing`
      : zone.held
        ? `${zone.held} seats held by bags`
        : zone.free_soon
          ? `${zone.free_soon} likely free soon`
          : "Nothing to flag";
  return (
    <div className={cx("flex flex-col gap-3 py-[22px]", !first && "border-t border-line", zone.freshness === "stale" && "opacity-75")}>
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-lg font-bold">{zone.name}</span>
          <span className="text-[13px] text-muted">{note}</span>
        </div>
        <div className="text-right">
          <span className="font-display text-[34px] font-extrabold leading-none tracking-[-0.04em]">
            {live ? <ApproxNumber value={`~${count(zone.free)}`} /> : "—"}
          </span>
          <div className={cx("mt-0.5 text-[13px] font-semibold", wordTone)}>{word}</div>
        </div>
      </div>
      {live ? (
        <SeatStrip total={zone.seats} taken={zone.occupied ?? 0} held={zone.held ?? 0} hidden={zone.unknown ?? 0} height={14} />
      ) : (
        <EmptyStrip height={14} />
      )}
      <div className="flex flex-wrap gap-x-[22px] gap-y-1 text-[13px] text-muted">
        <span>
          <b className="text-ink">{count(zone.occupied)}</b> taken
        </span>
        <span>
          <b className="text-busy">{count(zone.held)}</b> held by bags
        </span>
        <span>
          <b className="text-ink-2">{count(zone.unknown)}</b> hidden
        </span>
        <span>
          <b className="text-ink">{count(zone.free_soon)}</b> free soon
        </span>
        <span className="ml-auto">{zone.seats} seats</span>
      </div>
    </div>
  );
}

const LEGEND: { swatch: string; label: string }[] = [
  { swatch: "bg-brand", label: "Taken" },
  { swatch: "held-stripes", label: "Held by bags" },
  { swatch: "bg-hidden", label: "Hidden" },
  { swatch: "bg-card shadow-[inset_0_0_0_1.5px_var(--color-brand)]", label: "Free" },
];

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
    <Panel title="Stay times" aside={<SampleBadge>Experimental</SampleBadge>}>
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
      <Panel
        title="By zone"
        aside={
          <div className="flex flex-wrap gap-4 text-[13px] text-muted">
            {LEGEND.map((l) => (
              <span key={l.label} className="inline-flex items-center gap-2">
                <span className={cx("h-2 w-3.5 rounded-full", l.swatch)} />
                {l.label}
              </span>
            ))}
          </div>
        }
      >
        {seats.data && seats.data.zones.length > 0 ? (
          <div className="flex flex-col">
            {seats.data.zones.map((z, i) => (
              <ZoneRow key={z.zone_id} zone={z} first={i === 0} />
            ))}
          </div>
        ) : (
          <span className="text-sm text-muted">No seat data for this canteen yet.</span>
        )}
        <div className="mt-2 flex items-center gap-[18px] rounded-[18px] bg-page px-[18px] py-3">
          <TableScene width={96} />
          <p className="m-0 text-[13.5px] leading-[1.45] text-muted">
            Hidden and held seats are never shown to students as free. A seat only counts as free when the camera clearly sees it empty.
          </p>
        </div>
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
