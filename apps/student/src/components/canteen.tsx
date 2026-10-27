import type { BusyPoint, CanteenSummary, Freshness, ZoneOccupancy } from "@dinemate/api-client";
import { CanteenArt, cx, formatAgo, formatClock, Icon, levelFor, Ring, StatusPill } from "@dinemate/ui";
import { Link } from "react-router";
import { canteenInitial, canteenWall, freeShort, hasNumbers, rangeText } from "../lib/present";

export function freshnessText(freshness: Freshness, updatedAt: string, now: number): string {
  const ago = formatAgo(updatedAt, now);
  if (freshness === "live") return `Live · updated ${ago}`;
  if (freshness === "stale") return `Last updated ${ago} — may be out of date`;
  return `No live data · last reading ${ago}`;
}

function metaLine(c: CanteenSummary, now: number): string {
  if (!hasNumbers(c)) return "No info right now";
  const base = `${freeShort(c)} ${rangeText(c)} · ${formatAgo(c.updated_at, now)}`;
  return c.freshness === "stale" ? `${base} — may be out of date` : base;
}

export function CanteenRow({ canteen, now }: { canteen: CanteenSummary; now: number }) {
  return (
    <Link
      to={`/canteens/${canteen.id}`}
      className="flex items-center gap-3 rounded-[18px] border border-line bg-card p-2.5 text-ink no-underline hover:border-mint-line"
    >
      <div className="h-16 w-16 shrink-0">
        <CanteenArt wall={canteenWall(canteen.id)} label={canteenInitial(canteen.name)} className="rounded-[14px]" />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="text-[15px] font-extrabold">{canteen.name}</span>
        <StatusPill level={canteen.level} freshness={canteen.freshness} size="sm" className="self-start" />
        <span className={cx("text-xs text-muted", canteen.freshness === "stale" && "opacity-70")}>{metaLine(canteen, now)}</span>
      </div>
      <Ring
        percent={canteen.percent}
        level={canteen.level}
        freshness={canteen.freshness}
        size={54}
        thickness={6}
        textClassName="text-[13px]"
      />
    </Link>
  );
}

export function CanteenCard({ canteen, now }: { canteen: CanteenSummary; now: number }) {
  return (
    <Link
      to={`/canteens/${canteen.id}`}
      className="flex flex-[1_1_300px] flex-col gap-3.5 rounded-[22px] border border-line bg-card p-3 text-ink no-underline hover:border-mint-line"
    >
      <div className="h-[150px]">
        <CanteenArt wall={canteenWall(canteen.id)} label={canteenInitial(canteen.name)} className="rounded-2xl" />
      </div>
      <div className="flex items-center gap-3.5 px-1.5 pb-1.5">
        <Ring
          percent={canteen.percent}
          level={canteen.level}
          freshness={canteen.freshness}
          size={72}
          thickness={8}
          textClassName="text-base"
        />
        <div className="flex flex-1 flex-col gap-[5px]">
          <div className="flex items-center justify-between gap-2">
            <span className="text-lg font-extrabold">{canteen.name}</span>
            <StatusPill level={canteen.level} freshness={canteen.freshness} />
          </div>
          <span className={cx("text-sm text-ink-2", canteen.freshness === "stale" && "opacity-70")}>
            {hasNumbers(canteen) ? (
              <>
                <strong>{freeShort(canteen)}</strong> <span className="text-muted">{rangeText(canteen)}</span>
              </>
            ) : (
              "No info right now"
            )}
          </span>
          <span className="text-xs text-muted">
            {canteen.zones_live} of {canteen.zones_total} zones live · {formatAgo(canteen.updated_at, now)}
          </span>
        </div>
      </div>
    </Link>
  );
}

export function BestSpotMobile({ canteen }: { canteen: CanteenSummary }) {
  return (
    <section aria-label="Best spot now" className="flex flex-col overflow-hidden rounded-[22px] border border-line bg-card">
      <div className="relative h-32">
        <CanteenArt wall={canteenWall(canteen.id)} />
        <BestBadge className="absolute left-3 top-3" />
      </div>
      <div className="flex flex-col gap-2.5 px-4 pb-4 pt-3.5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="m-0 text-xl font-extrabold">{canteen.name}</h2>
          <StatusPill level={canteen.level} freshness={canteen.freshness} />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2">
          <span className="inline-flex items-center gap-1.5">
            <Icon name="seat" size={17} />
            <strong>{freeShort(canteen)}</strong>
            <span className="text-muted">{rangeText(canteen)}</span>
          </span>
          {canteen.walk ? (
            <span className="inline-flex items-center gap-1.5 text-muted">
              <Icon name="walk" size={17} />
              {canteen.walk.minutes} min walk
            </span>
          ) : null}
        </div>
        <Link
          to={`/canteens/${canteen.id}`}
          className="flex min-h-12 items-center justify-center gap-1.5 rounded-[14px] bg-brand text-[15px] font-bold text-white no-underline hover:bg-brand-dark hover:text-white"
        >
          View {canteen.name}
          <Icon name="arrowRight" size={16} strokeWidth={2.4} />
        </Link>
      </div>
    </section>
  );
}

export function BestSpotWeb({ canteen }: { canteen: CanteenSummary }) {
  return (
    <section aria-label="Best spot now" className="flex min-w-0 flex-[2_1_560px] flex-wrap items-center gap-6 rounded-[26px] bg-mint p-6">
      <div className="flex flex-[1_1_260px] flex-col gap-3.5">
        <BestBadge large />
        <h2 className="m-0 text-4xl font-extrabold tracking-[-0.03em] text-brand-dark">{canteen.name}</h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2.5 text-[15px]">
          <StatusPill level={canteen.level} freshness={canteen.freshness} size="lg" onWhite />
          <span className="inline-flex items-center gap-1.5 text-ink-2">
            <Icon name="seat" size={18} />
            <strong>{hasNumbers(canteen) ? `~${canteen.free_about} seats free` : "No info right now"}</strong>
            {hasNumbers(canteen) ? (
              <span className="text-muted">
                (est. {canteen.free_range[0]}–{canteen.free_range[1]})
              </span>
            ) : null}
          </span>
        </div>
        <span className="inline-flex items-center gap-1.5 text-sm text-muted">
          <Icon name="walk" size={16} />
          {canteen.walk ? `${canteen.walk.minutes} min walk from ${canteen.walk.from_name} · ` : ""}
          {canteen.shops_open} of {canteen.shops_total} shops open
        </span>
        <Link
          to={`/canteens/${canteen.id}`}
          className="inline-flex min-h-12 items-center gap-2 self-start rounded-[14px] bg-brand px-5 text-[15px] font-extrabold text-white no-underline hover:bg-brand-dark hover:text-white"
        >
          View details
          <Icon name="arrowRight" size={16} strokeWidth={2.4} />
        </Link>
      </div>
      <div className="h-[230px] flex-[1_1_300px]">
        <CanteenArt wall="#CFE9D7" label={canteenInitial(canteen.name)} className="rounded-[20px]" />
      </div>
    </section>
  );
}

function BestBadge({ className, large }: { className?: string; large?: boolean }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 self-start rounded-full bg-card font-extrabold text-brand-dark",
        large ? "px-3 py-1.5 text-[13px]" : "px-2.5 py-[5px] text-xs",
        className,
      )}
    >
      <Icon name="star" size={large ? 14 : 13} className="text-brand" />
      Best spot now
    </span>
  );
}

export function NoBestSpot({ anyLive }: { anyLive: boolean }) {
  return (
    <section
      aria-label="Best spot now"
      className="flex items-start gap-3 rounded-[22px] border-[1.5px] border-dashed border-dash bg-surface-soft p-4"
    >
      <Icon name="question" size={22} className="mt-0.5 shrink-0 text-neutral-ink" />
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-extrabold">{anyLive ? "No reliable alternative right now" : "No seat info right now"}</span>
        <span className="text-[13px] text-muted">
          {anyLive ? "Every canteen with live data is crowded." : "We'll show seats again as soon as live readings return."}
        </span>
      </span>
    </section>
  );
}

export function BusyTimesChart({ title, points }: { title: string; points: BusyPoint[] }) {
  return (
    <section aria-label={title} className="flex min-w-0 flex-[1.3_1_400px] flex-col gap-3.5 rounded-[22px] border border-line bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="m-0 text-[17px] font-extrabold">{title}</h2>
        <div className="flex gap-3 text-xs text-ink-2">
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
                "w-full max-w-[46px] rounded-t-lg rounded-b",
                p.is_forecast ? "forecast-stripes" : p.is_now ? "bg-busy-mark" : "bg-brand",
              )}
              style={{ height: Math.round(p.percent * 1.2) }}
            />
            <span aria-hidden="true" className={cx("text-[11px]", p.is_now ? "font-extrabold text-ink" : "text-muted")}>
              {p.label}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ZoneBarRow({ zone, last }: { zone: ZoneOccupancy; last: boolean }) {
  const style = levelFor(zone.level, zone.freshness);
  const numbers = hasNumbers(zone);
  return (
    <li className={cx("flex items-center gap-3 py-3", !last && "border-b border-line-soft")}>
      <div className="flex flex-1 flex-col gap-1.5">
        <div className="flex justify-between gap-2">
          <span className="text-sm font-bold">{zone.name}</span>
          <span className={cx("text-[13px] text-muted", zone.freshness === "stale" && "opacity-70")}>
            {numbers ? `${freeShort(zone)} ${rangeText(zone)}` : "No info right now"}
          </span>
        </div>
        <div
          aria-hidden="true"
          className={cx(
            "h-[7px] overflow-hidden rounded bg-track",
            !numbers && "outline outline-1 -outline-offset-1 outline-dashed outline-dash",
          )}
        >
          {numbers ? (
            <div
              className={cx("h-full rounded", style.bar, zone.freshness === "stale" && "opacity-50")}
              style={{ width: `${zone.percent}%` }}
            />
          ) : null}
        </div>
      </div>
      <span className="w-10 text-right text-sm font-extrabold">{numbers ? `${zone.percent}%` : "—"}</span>
    </li>
  );
}

export function ZoneCard({ zone, now }: { zone: ZoneOccupancy; now: number }) {
  const numbers = hasNumbers(zone);
  return (
    <div
      className={cx(
        "flex flex-[1_1_300px] items-center gap-4 rounded-[22px] p-5",
        numbers ? "border border-line bg-card" : "border-[1.5px] border-dashed border-dash bg-surface-soft",
      )}
    >
      <Ring percent={zone.percent} level={zone.level} freshness={zone.freshness} size={80} thickness={9} textClassName="text-[17px]" />
      <div className="flex flex-1 flex-col gap-[5px]">
        <span className="text-[17px] font-extrabold">{zone.name}</span>
        <StatusPill level={zone.level} freshness={zone.freshness} className="self-start" />
        <span className="text-[13px] text-muted">
          {numbers
            ? `${freeShort(zone)} ${rangeText(zone)} of ${zone.capacity} seats${zone.freshness === "stale" ? ` · ${formatAgo(zone.updated_at, now)}` : ""}`
            : `${zone.capacity} seats · sensor offline since ${formatClock(zone.updated_at)}`}
        </span>
      </div>
    </div>
  );
}
