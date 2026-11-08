import {
  ApiError,
  useCanteen,
  useServerNow,
  useStudentSummary,
  type CanteenDetail,
  type CanteenSummary,
  type ForecastPoint,
  type OpeningHours,
} from "@dinemate/api-client";
import {
  CanteenArt,
  canteenPhotoFor,
  cx,
  FoodArt,
  formatClock,
  formatClock24,
  formatLocalRange,
  Icon,
  levelFor,
  LiveLine,
  shopPhotoFor,
  StatusPill,
  type IconName,
} from "@dinemate/ui";
import type { ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { AlternativeCard, freshnessText, SeatLegend, Strip, useHeldSeats, useZoneSeats, ZoneBarRow, ZoneCard } from "../components/canteen";
import { Footnote, Loading, MessageCard, OfflineCard, ShopStatusText, Skeleton } from "../components/common";
import { useIsDesktop, useOnline } from "../lib/device";
import { favourites } from "../lib/prefs";
import { canteenInitial, canteenStrip, canteenWall, hasNumbers } from "../lib/present";

function isOpenNow(hours: OpeningHours[], now: number): boolean {
  const hm = formatClock24(now);
  return hours.some((h) => hm >= h.opens && hm < h.closes);
}

function hoursText(hours: OpeningHours[]): string {
  const first = hours[0];
  return first ? formatLocalRange(first.opens, first.closes) : "Hours not available";
}

function shortClock(iso: string): string {
  return formatClock(iso).split(" ")[0] ?? "";
}

export function CanteensIndex() {
  const summary = useStudentSummary();
  if (!summary.data) {
    return (
      <Loading label="Loading canteens">
        <Skeleton className="m-4 h-[250px]" />
      </Loading>
    );
  }
  const target = summary.data.best?.canteen_id ?? summary.data.canteens[0]?.id;
  return target ? (
    <Navigate to={`/canteens/${target}`} replace />
  ) : (
    <MessageCard icon="question" art="no-canteens" title="No canteens yet" className="m-4" />
  );
}

export function CanteenScreen() {
  const { id = "" } = useParams();
  const detail = useCanteen(id);
  const now = useServerNow(1000);
  const isDesktop = useIsDesktop();
  const online = useOnline();
  if (detail.error instanceof ApiError && detail.error.status === 404) {
    return (
      <main id="main" className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 p-6">
        <MessageCard icon="question" art="page-not-found" title="Canteen not found" body="It may have been renamed or removed." />
        <Link to="/" className="font-bold text-brand">
          Back to home
        </Link>
      </main>
    );
  }
  const data = detail.data;
  if (!data) {
    return (
      <main id="main" className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 p-4 md:p-6">
        <Loading label="Loading canteen">
          <Skeleton className="h-[250px] md:h-[340px]" />
          <Skeleton className="h-[200px]" />
        </Loading>
      </main>
    );
  }
  return isDesktop ? <CanteenWeb data={data} now={now} online={online} /> : <CanteenMobile data={data} now={now} online={online} />;
}

interface ViewProps {
  data: CanteenDetail;
  now: number;
  online: boolean;
}

function FavouriteButton({ canteen, className }: { canteen: CanteenSummary; className?: string }) {
  const saved = favourites.use().includes(canteen.id);
  const toggle = () => favourites.set((prev) => (saved ? prev.filter((x) => x !== canteen.id) : [...prev, canteen.id]));
  return (
    <button
      type="button"
      aria-pressed={saved}
      aria-label={saved ? `Remove ${canteen.name} from favourites` : `Save ${canteen.name} to favourites`}
      onClick={toggle}
      className={cx("flex items-center justify-center border-0 bg-card/90 text-crowd-mark", className)}
    >
      <Icon name={saved ? "heartSolid" : "heart"} size={20} strokeWidth={2.2} />
    </button>
  );
}

function BackButton({ className }: { className?: string }) {
  const navigate = useNavigate();
  const goBack = () => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else navigate("/");
  };
  return (
    <button
      type="button"
      aria-label="Back"
      onClick={goBack}
      className={cx("flex items-center justify-center border-0 bg-card/90 text-ink", className)}
    >
      <Icon name="arrowLeft" size={20} strokeWidth={2.2} />
    </button>
  );
}

function Tile({ icon, title, sub, to, className }: { icon: IconName; title: string; sub: string; to?: string; className?: string }) {
  const body: ReactNode = (
    <>
      <Icon name={icon} size={18} className="text-brand" />
      <span className="text-xs font-bold md:text-[13px]">{title}</span>
      <span className="text-xs text-muted">{sub}</span>
    </>
  );
  const base = cx("flex flex-col gap-1 rounded-2xl p-2.5 md:p-3", className);
  return to ? (
    <Link to={to} className={cx(base, "text-ink no-underline hover:outline hover:outline-1 hover:outline-mint-line")}>
      {body}
    </Link>
  ) : (
    <div className={base}>{body}</div>
  );
}

function SeatHeadline({ canteen, large }: { canteen: CanteenSummary; large?: boolean }) {
  const numbers = hasNumbers(canteen);
  return (
    <div className={cx("shrink-0 text-right", canteen.freshness === "stale" && "opacity-60")}>
      <div className={cx("font-display font-extrabold leading-[0.85] tracking-[-0.05em]", large ? "text-[72px]" : "text-[52px]")}>
        {numbers ? `~${canteen.free_about}` : "—"}
      </div>
      <div className="mt-1.5 text-xs text-muted">{numbers ? `of ${canteen.monitored_capacity} seats free` : "no live number"}</div>
    </div>
  );
}

function SeatSummary({ canteen }: { canteen: CanteenSummary }) {
  const held = useHeldSeats(canteen.id);
  const counts = canteenStrip(canteen, held);
  return (
    <section aria-label="Seat estimate" className="flex flex-col gap-2.5">
      <Strip counts={counts} height={12} stale={canteen.freshness === "stale"} />
      {counts ? (
        <SeatLegend counts={counts} free={hasNumbers(canteen) ? `~${canteen.free_about}` : "—"} />
      ) : (
        <span className="text-[13px] text-muted">Seat numbers are hidden until live readings return.</span>
      )}
    </section>
  );
}

function ForecastTip({ point }: { point: ForecastPoint }) {
  return (
    <div className="flex items-center gap-3.5 rounded-[20px] bg-purple-bg px-4 py-3.5">
      <div aria-hidden="true" className="flex h-[34px] items-end gap-1">
        {[30, 24, 17, 10].map((h, i) => (
          <span key={h} className="block w-2 rounded-[3px] bg-purple" style={{ height: h, opacity: 1 - i * 0.2 }} />
        ))}
      </div>
      <div className="flex flex-col">
        <span className="text-sm font-bold text-purple-deep">
          Likely {point.low}–{point.high}% at {formatClock(point.at)}
        </span>
        <span className="text-xs text-purple-ink">Experimental forecast</span>
      </div>
    </div>
  );
}

function CanteenMobile({ data, now, online }: ViewProps) {
  const { canteen, zones, forecast, hours_today } = data;
  const seats = useZoneSeats(canteen.id);
  const firstForecast = forecast[0];
  return (
    <main id="main" className="flex flex-1 flex-col">
      <div className="relative h-[250px] shrink-0">
        <CanteenArt wall={canteenWall(canteen.id)} photo={canteenPhotoFor(canteen.id)} />
        <BackButton className="absolute left-4 top-[18px] h-[42px] w-[42px] rounded-[14px]" />
        <FavouriteButton canteen={canteen} className="absolute right-4 top-[18px] h-[42px] w-[42px] rounded-[14px]" />
      </div>
      <div className="relative -mt-9 flex flex-col gap-4 rounded-t-[28px] bg-page px-[18px] py-[22px]">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-2">
            <h1 className="m-0 font-display text-[32px] font-extrabold leading-none tracking-[-0.04em]">{canteen.name}</h1>
            <div className="flex flex-wrap gap-2">
              <StatusPill level={canteen.level} freshness={canteen.freshness} size="sm" />
              <LiveLine freshness={canteen.freshness} text={freshnessText(canteen.freshness, canteen.updated_at, now)} />
            </div>
          </div>
          {online ? <SeatHeadline canteen={canteen} /> : null}
        </div>
        {online ? <SeatSummary canteen={canteen} /> : <OfflineCard />}
        {online ? <AlternativeCard canteen={canteen} /> : null}
        <div className="grid grid-cols-3 gap-2">
          <Tile
            icon="clock"
            title={isOpenNow(hours_today, now) ? "Open now" : "Closed now"}
            sub={hoursText(hours_today)}
            className="raised border border-line bg-card"
          />
          <Tile
            icon="store"
            title={`${canteen.shops_total} shops`}
            sub={`${canteen.shops_open} open now`}
            to={`/food?canteen=${canteen.id}`}
            className="raised border border-line bg-card"
          />
          {canteen.walk ? (
            <Tile
              icon="walk"
              title={`${canteen.walk.minutes} min`}
              sub={`from ${canteen.walk.from_name}`}
              className="raised border border-line bg-card"
            />
          ) : (
            <Tile
              icon="camera"
              title={`${canteen.zones_live} of ${canteen.zones_total} zones`}
              sub="with live data"
              className="raised border border-line bg-card"
            />
          )}
        </div>
        <div className="mt-1 flex items-baseline justify-between">
          <h2 className="m-0 text-[22px] font-semibold">Seats by zone</h2>
          <span className="text-[13px] text-muted">{zones.length} zones</span>
        </div>
        {online ? (
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {zones.map((z, i) => (
              <ZoneBarRow key={z.zone_id} zone={z} last={i === zones.length - 1} seats={seats.get(z.zone_id)} now={now} />
            ))}
          </ul>
        ) : null}
        {online && firstForecast && canteen.freshness === "live" ? <ForecastTip point={firstForecast} /> : null}
      </div>
    </main>
  );
}

function NextHour({ canteen, forecast }: { canteen: CanteenSummary; forecast: ForecastPoint[] }) {
  const nowMark = levelFor(canteen.level, canteen.freshness).bar;
  return (
    <section
      aria-labelledby="fc-title"
      className="raised flex min-w-0 flex-[1.2_1_420px] flex-col gap-3.5 rounded-[22px] border border-line bg-card p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="fc-title" className="m-0 text-[17px] font-extrabold">
          Next hour
        </h2>
        <span className="inline-flex h-7 items-center rounded-full bg-purple-bg px-3 text-xs font-bold text-purple-ink">
          Experimental forecast
        </span>
      </div>
      <ul className="m-0 flex h-[140px] list-none items-end gap-3.5 p-0">
        {canteen.percent !== null ? (
          <li className="flex flex-1 flex-col items-center gap-1.5">
            <span className="text-xs font-extrabold">{canteen.percent}%</span>
            <div
              aria-hidden="true"
              className={cx("w-full max-w-16 rounded-t-[10px] rounded-b", nowMark)}
              style={{ height: Math.round(canteen.percent * 1.2) }}
            />
            <span className="text-xs font-extrabold">Now</span>
          </li>
        ) : null}
        {forecast.map((p) => (
          <li key={p.at} className="flex flex-1 flex-col items-center gap-1.5">
            <span className="text-xs text-muted">
              {p.low}–{p.high}%
            </span>
            <div
              aria-hidden="true"
              className="w-full max-w-16 rounded-t-[10px] rounded-b border-[1.5px] border-dashed border-purple bg-purple-bg"
              style={{ height: Math.round(((p.low + p.high) / 2) * 1.2) }}
            />
            <span className="text-xs text-muted">{shortClock(p.at)}</span>
          </li>
        ))}
      </ul>
      <p className="m-0 text-xs text-muted">Based on today's readings and past weekdays. Not yet evaluated — treat as a rough guide.</p>
    </section>
  );
}

function CanteenWeb({ data, now, online }: ViewProps) {
  const { canteen, zones, forecast, hours_today, shops } = data;
  const seats = useZoneSeats(canteen.id);
  return (
    <main id="main" className="mx-auto flex max-w-[1200px] flex-col gap-[22px] px-6 pb-10 pt-[22px]">
      <Link
        to="/"
        className="inline-flex min-h-9 items-center gap-1.5 self-start text-sm font-bold text-brand no-underline hover:text-brand-dark"
      >
        <Icon name="arrowLeft" size={16} strokeWidth={2.4} />
        All canteens
      </Link>
      <div className="flex flex-wrap gap-[22px]">
        <div className="relative h-[340px] flex-[1_1_460px]">
          <CanteenArt
            wall={canteenWall(canteen.id)}
            photo={canteenPhotoFor(canteen.id)}
            label={canteenInitial(canteen.name)}
            className="rounded-[26px]"
          />
          <FavouriteButton canteen={canteen} className="absolute right-4 top-4 h-11 w-11 rounded-[14px]" />
        </div>
        <section
          aria-label={`${canteen.name} summary`}
          className="raised flex min-w-0 flex-[1_1_420px] flex-col gap-5 rounded-[26px] border border-line bg-card p-6"
        >
          <div className="flex flex-wrap items-start justify-between gap-2.5">
            <div className="flex flex-col gap-1">
              <h1 className="m-0 font-display text-[44px] font-extrabold leading-none tracking-[-0.04em]">{canteen.name}</h1>
              <div className="flex flex-wrap gap-2">
                <StatusPill level={canteen.level} freshness={canteen.freshness} />
                <LiveLine freshness={canteen.freshness} text={freshnessText(canteen.freshness, canteen.updated_at, now)} />
              </div>
            </div>
            {online ? <SeatHeadline canteen={canteen} large /> : null}
          </div>
          {online ? <SeatSummary canteen={canteen} /> : <OfflineCard />}
          <div className="grid grid-cols-3 gap-2.5">
            <Tile
              icon="clock"
              title={isOpenNow(hours_today, now) ? "Open now" : "Closed now"}
              sub={hoursText(hours_today)}
              className="bg-page"
            />
            <Tile
              icon="store"
              title={`${canteen.shops_total} shops`}
              sub={`${canteen.shops_open} open now`}
              to={`/food?canteen=${canteen.id}`}
              className="bg-page"
            />
            <Tile icon="camera" title={`${canteen.zones_live} of ${canteen.zones_total} zones`} sub="with live data" className="bg-page" />
          </div>
        </section>
      </div>
      <h2 className="m-0 mt-1 text-[26px] font-semibold">Seats by zone</h2>
      {online ? (
        <div className="flex flex-wrap gap-5">
          {zones.map((z) => (
            <ZoneCard key={z.zone_id} zone={z} now={now} seats={seats.get(z.zone_id)} />
          ))}
        </div>
      ) : (
        <OfflineCard />
      )}
      <div className="flex flex-wrap gap-5">
        {online ? <AlternativeCard canteen={canteen} /> : null}
        {online && forecast.length > 0 && canteen.freshness === "live" ? <NextHour canteen={canteen} forecast={forecast} /> : null}
        <section
          aria-labelledby="shops-title"
          className="raised flex min-w-0 flex-[1_1_360px] flex-col gap-1 rounded-[22px] border border-line bg-card p-5"
        >
          <div className="mb-1.5 flex items-center justify-between">
            <h2 id="shops-title" className="m-0 text-[17px] font-extrabold">
              Shops in {canteen.name}
            </h2>
            <Link to={`/food?canteen=${canteen.id}`} className="text-[13px] font-bold text-brand no-underline hover:text-brand-dark">
              Menus
            </Link>
          </div>
          {shops.length === 0 ? <span className="text-sm text-muted">No shops listed yet</span> : null}
          <ul className="m-0 flex list-none flex-col p-0">
            {shops.map((shop, i) => (
              <li key={shop.id} className={i < shops.length - 1 ? "border-b border-line-soft" : undefined}>
                <Link
                  to={`/food?canteen=${canteen.id}&shop=${shop.id}`}
                  className="flex min-h-[52px] items-center justify-between gap-2 text-ink no-underline hover:text-brand-dark"
                >
                  <span className="flex items-center gap-2.5">
                    <FoodArt photo={shopPhotoFor(shop.id, shop.kind)} className="h-9 w-9 shrink-0 rounded-[10px]" />
                    <span className="text-sm font-bold">{shop.name}</span>
                  </span>
                  <ShopStatusText status={shop.status} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <Footnote className="text-[13px]">
        {canteen.is_sample
          ? "Sample data · seat counts are estimates · shop names, hours, prices and pictures are placeholders"
          : "Seat counts are estimates from privacy-preserving sensors."}
      </Footnote>
    </main>
  );
}
