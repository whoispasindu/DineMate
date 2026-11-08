import {
  useCanteenSeats,
  useRecommendation,
  useSeatOverview,
  type BusyPoint,
  type CanteenSummary,
  type Freshness,
  type ZoneOccupancy,
  type ZoneSeats,
} from "@dinemate/api-client";
import {
  ApproxNumber,
  CanteenArt,
  canteenPhotoFor,
  cx,
  EmptyStrip,
  emptyArtFor,
  formatAgo,
  formatClock,
  Icon,
  levelFor,
  SeatStrip,
  StatusPill,
} from "@dinemate/ui";
import { Link } from "react-router";
import { useMemo } from "react";
import { canteenInitial, canteenStrip, canteenWall, hasNumbers, seatNote, zoneStrip, type StripCounts } from "../lib/present";

export function freshnessText(freshness: Freshness, updatedAt: string | null, now: number): string {
  if (updatedAt === null) return "No live data yet";
  const ago = formatAgo(updatedAt, now);
  if (freshness === "live") return `Live · ${ago}`;
  if (freshness === "stale") return `Updated ${ago} — may be out of date`;
  return `No live data · last reading ${ago}`;
}

export function useHeldSeats(canteenId: string): number {
  const overview = useSeatOverview();
  return overview.data?.items.find((i) => i.canteen_id === canteenId)?.held ?? 0;
}

export function useZoneSeats(canteenId: string): Map<string, ZoneSeats> {
  const seats = useCanteenSeats(canteenId);
  return useMemo(() => new Map((seats.data?.zones ?? []).map((z) => [z.zone_id, z])), [seats.data]);
}

function heldNote(held: number): string | null {
  return held > 0 ? `${held} held by bags` : null;
}

function rowNote(c: CanteenSummary, held: number, now: number): string {
  if (!hasNumbers(c)) return c.updated_at ? `Last reading ${formatAgo(c.updated_at, now)}` : "No live data yet";
  if (c.freshness === "stale") return `Updated ${formatAgo(c.updated_at, now)}`;
  if (c.level === "crowded" || c.level === "near_capacity") return "Few or no seats";
  return heldNote(held) ?? `${c.zones_live} of ${c.zones_total} zones live`;
}

export function Strip({
  counts,
  dark,
  height = 8,
  stale,
}: {
  counts: StripCounts | null;
  dark?: boolean;
  height?: number;
  stale?: boolean;
}) {
  return counts ? <SeatStrip {...counts} dark={dark} height={height} stale={stale} /> : <EmptyStrip height={height} />;
}

function BigNumber({ value, className }: { value: string; className?: string }) {
  return (
    <span className={cx("font-display font-extrabold leading-none tracking-[-0.04em]", className)}>
      <ApproxNumber value={value} />
    </span>
  );
}

function freeAbout(c: Pick<CanteenSummary, "free_about" | "free_range" | "freshness">): string {
  return hasNumbers(c) ? `~${c.free_about}` : "—";
}

function rangeLine(c: Pick<CanteenSummary, "free_about" | "free_range" | "freshness">): string {
  return hasNumbers(c) ? `${c.free_range[0]}–${c.free_range[1]} free` : "No number";
}

function seatsLabel(c: Pick<CanteenSummary, "name" | "free_about" | "free_range" | "freshness">): string {
  return hasNumbers(c)
    ? `${c.name}: about ${c.free_about} seats free, between ${c.free_range[0]} and ${c.free_range[1]}`
    : `${c.name}: no live seat number right now`;
}

export function CanteenRow({ canteen, now }: { canteen: CanteenSummary; now: number }) {
  const held = useHeldSeats(canteen.id);
  const stale = canteen.freshness === "stale";
  return (
    <Link to={`/canteens/${canteen.id}`} className="flex items-center gap-3.5 py-3.5 text-ink no-underline hover:opacity-90">
      <div className="relative h-[58px] w-[58px] shrink-0">
        <CanteenArt wall={canteenWall(canteen.id)} photo={canteenPhotoFor(canteen.id)} className="rounded-2xl" />
        <span
          aria-hidden="true"
          className="absolute -left-1.5 -top-1.5 flex h-[22px] min-w-[22px] items-center justify-center rounded-lg bg-brand px-1 font-display text-xs font-extrabold text-sand"
        >
          {canteenInitial(canteen.name)}
        </span>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <span className="text-base font-bold">{canteen.name}</span>
        <Strip counts={canteenStrip(canteen, held)} height={5} stale={stale} />
        <div className="flex min-w-0 items-center gap-2">
          <StatusPill level={canteen.level} freshness={canteen.freshness} size="sm" />
          <span className="truncate text-[13px] text-faint">{rowNote(canteen, held, now)}</span>
        </div>
      </div>
      <div aria-hidden="true" className={cx("w-[78px] shrink-0 whitespace-nowrap text-right", stale && "opacity-60")}>
        <BigNumber value={freeAbout(canteen)} className="text-[30px]" />
        <div className="mt-1 text-xs text-muted">{rangeLine(canteen)}</div>
      </div>
    </Link>
  );
}

export function CanteenCard({ canteen, now }: { canteen: CanteenSummary; now: number }) {
  const held = useHeldSeats(canteen.id);
  const stale = canteen.freshness === "stale";
  return (
    <Link
      to={`/canteens/${canteen.id}`}
      className="raised flex flex-[1_1_300px] flex-col gap-4 rounded-[22px] border border-line bg-card p-3 text-ink no-underline hover:border-mint-line"
    >
      <div className="h-[150px]">
        <CanteenArt
          wall={canteenWall(canteen.id)}
          photo={canteenPhotoFor(canteen.id)}
          label={canteenInitial(canteen.name)}
          className="rounded-2xl"
        />
      </div>
      <div className="flex flex-col gap-3 px-1.5 pb-1.5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <span className="text-lg font-bold">{canteen.name}</span>
            <StatusPill level={canteen.level} freshness={canteen.freshness} size="sm" className="self-start" />
          </div>
          <div aria-hidden="true" className={cx("whitespace-nowrap text-right", stale && "opacity-60")}>
            <BigNumber value={freeAbout(canteen)} className="text-[34px]" />
            <div className="mt-1 text-xs text-muted">{rangeLine(canteen)}</div>
          </div>
        </div>
        <Strip counts={canteenStrip(canteen, held)} stale={stale} />
        <span className="text-xs text-muted">{rowNote(canteen, held, now)}</span>
      </div>
    </Link>
  );
}

function BestBadge() {
  return (
    <span className="inline-flex h-7 items-center gap-1.5 self-start whitespace-nowrap rounded-full bg-purple/25 px-3 text-xs font-bold text-purple-soft">
      <span className="h-1.5 w-1.5 rounded-full bg-purple" />
      Best spot now
    </span>
  );
}

function BestSpotBody({ canteen, big }: { canteen: CanteenSummary; big?: boolean }) {
  const held = useHeldSeats(canteen.id);
  const counts = canteenStrip(canteen, held);
  return (
    <>
      <div className="flex items-end justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className={cx("m-0 font-sans font-semibold tracking-normal", big ? "text-[28px]" : "text-[17px]")}>{canteen.name}</h2>
          <span className="text-xs text-on-dark-faint">
            {canteen.walk
              ? `${canteen.walk.minutes} min walk from ${canteen.walk.from_name}`
              : `${canteen.shops_open} of ${canteen.shops_total} shops open`}
          </span>
        </div>
        <div className="text-right">
          <BigNumber value={freeAbout(canteen)} className={big ? "text-[96px] leading-[0.82]" : "text-[56px] leading-[0.82]"} />
          <div className="mt-1.5 text-xs text-on-dark-faint">
            {hasNumbers(canteen) ? `seats free · ${canteen.free_range[0]}–${canteen.free_range[1]}` : "no live number"}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-1 flex-col gap-2">
          <Strip counts={counts} dark />
          <span className="text-xs text-on-dark-faint">
            {canteen.percent !== null ? `${canteen.percent}% in use` : "Usage unknown"}
            {held > 0 ? ` · ${held} held by bags` : ""}
          </span>
        </div>
        <Link
          to={`/canteens/${canteen.id}`}
          className="edge-sand inline-flex h-[42px] shrink-0 items-center gap-2 rounded-[14px] bg-sand px-3.5 text-sm font-bold text-brand no-underline hover:text-brand"
        >
          {canteen.walk ? (
            <>
              <Icon name="walk" size={18} strokeWidth={2} />
              {canteen.walk.minutes} min
            </>
          ) : (
            <>
              View
              <Icon name="arrowRight" size={16} strokeWidth={2.2} />
            </>
          )}
          <span className="sr-only">, open {canteen.name}</span>
        </Link>
      </div>
    </>
  );
}

export function BestSpotMobile({ canteen }: { canteen: CanteenSummary }) {
  return (
    <section aria-label="Best spot now" className="slab flex flex-col gap-3 rounded-[24px] bg-brand px-[18px] pb-3.5 pt-4 text-sand">
      <BestBadge />
      <BestSpotBody canteen={canteen} />
    </section>
  );
}

export function BestSpotWeb({ canteen }: { canteen: CanteenSummary }) {
  return (
    <section
      aria-label="Best spot now"
      className="slab flex min-w-0 flex-[2_1_560px] flex-wrap items-stretch gap-6 rounded-[28px] bg-brand p-6 text-sand"
    >
      <div className="flex min-w-[280px] flex-[1_1_320px] flex-col justify-between gap-5">
        <BestBadge />
        <BestSpotBody canteen={canteen} big />
      </div>
      <div className="h-[230px] flex-[1_1_240px]">
        <CanteenArt wall="#2E5743" photo={canteenPhotoFor(canteen.id)} className="rounded-[20px]" />
      </div>
    </section>
  );
}

export function NoBestSpot({ anyLive }: { anyLive: boolean }) {
  const offlineArt = anyLive ? undefined : emptyArtFor("sensor-offline");
  return (
    <section
      aria-label="Best spot now"
      className="flex items-start gap-3 rounded-[22px] border-[1.5px] border-dashed border-dash bg-surface-soft p-4"
    >
      {offlineArt ? (
        <img src={offlineArt} alt="" loading="lazy" decoding="async" className="h-16 w-16 shrink-0 object-contain" />
      ) : (
        <Icon name="question" size={22} className="mt-0.5 shrink-0 text-neutral-ink" />
      )}
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-bold">{anyLive ? "No reliable alternative right now" : "No seat info right now"}</span>
        <span className="text-[13px] text-muted">
          {anyLive ? "Every canteen with live data is crowded." : "We'll show seats again as soon as live readings return."}
        </span>
      </span>
    </section>
  );
}

export function BusyTimesChart({ title, points }: { title: string; points: BusyPoint[] }) {
  return (
    <section
      aria-label={title}
      className="raised flex min-w-0 flex-[1.3_1_400px] flex-col gap-3.5 rounded-[22px] border border-line bg-card p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="m-0 text-xl font-semibold">{title}</h2>
        <div className="flex gap-3 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-[3px] bg-brand" />
            Measured
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="forecast-stripes h-2.5 w-2.5 rounded-[3px]" />
            Forecast (experimental)
          </span>
        </div>
      </div>
      <ul className="m-0 flex h-[150px] list-none items-end gap-2.5 p-0">
        {points.map((p) => (
          <li key={p.label} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
            <span className="sr-only">
              {p.label}: {p.is_forecast ? "forecast" : "measured"} {p.percent}%
            </span>
            <div
              aria-hidden="true"
              title={`${p.is_forecast ? "Forecast" : "Measured"} ${p.percent}%`}
              className={cx(
                "w-full max-w-[46px] rounded-t-md rounded-b-sm",
                p.is_forecast ? "forecast-stripes" : p.percent >= 80 ? "bg-crowd-mark" : "bg-brand",
              )}
              style={{ height: Math.round(p.percent * 1.2) }}
            />
            <span aria-hidden="true" className={cx("text-xs", p.is_now ? "font-bold text-ink" : "text-muted")}>
              {p.label}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function zoneNote(zone: ZoneOccupancy, seats: ZoneSeats | undefined, now: number): string {
  if (!hasNumbers(zone)) {
    return zone.updated_at ? `Camera offline since ${formatClock(zone.updated_at)}` : "Not monitored yet";
  }
  const note = seatNote(seats);
  if (note) return note;
  if (zone.freshness === "stale") return `Updated ${formatAgo(zone.updated_at, now)}`;
  return zone.level === "normal" ? "Plenty of room" : zone.level === "busy" ? "Filling up" : "Few or no seats right now";
}

function countsLine(counts: StripCounts | null, capacity: number): string {
  if (!counts) return `${capacity} seats`;
  const parts = [`${counts.taken} taken`];
  if (counts.held) parts.push(`${counts.held} held`);
  if (counts.hidden) parts.push(`${counts.hidden} hidden`);
  parts.push(`${counts.total} seats`);
  return parts.join(" · ");
}

function ZoneBody({ zone, seats, now, large }: { zone: ZoneOccupancy; seats?: ZoneSeats; now: number; large?: boolean }) {
  const style = levelFor(zone.level, zone.freshness);
  const counts = zoneStrip(zone, seats);
  const stale = zone.freshness === "stale";
  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className={cx("font-bold", large ? "text-lg" : "text-base")}>{zone.name}</span>
          <span className="text-[13px] text-muted">{zoneNote(zone, seats, now)}</span>
        </div>
        <div className={cx("shrink-0 whitespace-nowrap text-right", stale && "opacity-60")}>
          <BigNumber value={freeAbout(zone)} className={large ? "text-[34px]" : "text-[28px]"} />
          <div className="mt-1 text-xs text-muted">
            {hasNumbers(zone) ? `free · ${zone.free_range[0]}–${zone.free_range[1]}` : "no number"}
          </div>
        </div>
      </div>
      <Strip counts={counts} height={large ? 12 : 8} stale={stale} />
      <div className="flex justify-between gap-2 text-xs font-semibold">
        <span className={style.word}>{style.label}</span>
        <span className="text-faint">{countsLine(counts, zone.capacity)}</span>
      </div>
    </>
  );
}

export function ZoneBarRow({ zone, seats, now }: { zone: ZoneOccupancy; last?: boolean; seats?: ZoneSeats; now: number }) {
  return (
    <li
      aria-label={seatsLabel(zone)}
      className={cx(
        "flex flex-col gap-3 rounded-[22px] px-[18px] py-4",
        hasNumbers(zone) ? "raised border border-line bg-card" : "border-[1.5px] border-dashed border-dash bg-surface-soft",
      )}
    >
      <ZoneBody zone={zone} seats={seats} now={now} />
    </li>
  );
}

export function ZoneCard({ zone, now, seats }: { zone: ZoneOccupancy; now: number; seats?: ZoneSeats }) {
  return (
    <div
      role="group"
      aria-label={seatsLabel(zone)}
      className={cx(
        "flex flex-[1_1_300px] flex-col gap-3.5 rounded-[22px] p-5",
        hasNumbers(zone) ? "raised border border-line bg-card" : "border-[1.5px] border-dashed border-dash bg-surface-soft",
      )}
    >
      <ZoneBody zone={zone} seats={seats} now={now} large />
    </div>
  );
}

export function SeatLegend({ counts, free }: { counts: StripCounts | null; free: string }) {
  if (!counts) return null;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-1.5 w-3 rounded-full bg-brand" />
        {counts.taken} taken
      </span>
      {counts.held ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="held-stripes h-1.5 w-3 rounded-full" />
          {counts.held} held by bags
        </span>
      ) : null}
      {counts.hidden ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-3 rounded-full bg-hidden" />
          {counts.hidden} hidden
        </span>
      ) : null}
      <span className="inline-flex items-center gap-1.5">
        <span className="h-1.5 w-3 rounded-full border border-brand bg-card" />
        {free} free
      </span>
    </div>
  );
}

export function AlternativeCard({ canteen }: { canteen: CanteenSummary }) {
  const needsAlternative = canteen.freshness !== "live" || canteen.level === "crowded" || canteen.level === "near_capacity";
  const result = useRecommendation(canteen.id, needsAlternative);
  if (!needsAlternative || !result.data) return null;
  const pick = result.data.recommendation;
  if (!pick) {
    return (
      <section
        aria-label="Less crowded nearby"
        className="flex items-start gap-3 rounded-[22px] border-[1.5px] border-dashed border-dash bg-surface-soft p-4"
      >
        <Icon name="question" size={20} className="mt-0.5 shrink-0 text-neutral-ink" />
        <span className="text-[13px] font-bold text-ink-2">{result.data.message}</span>
      </section>
    );
  }
  return (
    <Link
      to={`/canteens/${pick.canteen_id}`}
      aria-label={`Less crowded nearby: ${pick.name}, about ${pick.free_about ?? pick.available_range[0]} seats free`}
      className="edge-ticket flex items-center gap-3 rounded-[20px] bg-sand p-4 text-ink no-underline"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand text-sand">
        <Icon name="walk" size={20} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-xs font-semibold text-muted">Less crowded nearby</span>
        <span className="text-[15px] font-bold">
          {pick.name} · about {pick.free_about ?? pick.available_range[0]} free
        </span>
        <span className="text-xs text-muted">
          {pick.available_range[0]}–{pick.available_range[1]} seats (est.)
          {pick.walk_minutes !== null ? ` · ${pick.walk_minutes} min walk` : ""}
        </span>
      </span>
      <Icon name="chevronRight" size={18} className="shrink-0 text-muted" />
    </Link>
  );
}
