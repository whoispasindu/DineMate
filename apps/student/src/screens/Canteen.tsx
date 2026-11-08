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
  HalfGauge,
  Icon,
  levelFor,
  LiveLine,
  shopPhotoFor,
  StatusPill,
  type IconName,
} from "@dinemate/ui";
import type { ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { AlternativeCard, freshnessText, useZoneSeats, ZoneBarRow, ZoneCard } from "../components/canteen";
import { Footnote, Loading, MessageCard, OfflineCard, ShopStatusText, Skeleton } from "../components/common";
import { useIsDesktop, useOnline } from "../lib/device";
import { favourites } from "../lib/prefs";
import { canteenInitial, canteenWall, hasNumbers } from "../lib/present";

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
      className={cx("flex items-center justify-center border-0 bg-card text-crowd-mark", className)}
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
      className={cx("flex items-center justify-center border-0 bg-card text-ink", className)}
    >
      <Icon name="arrowLeft" size={20} strokeWidth={2.2} />
    </button>
  );
}

function Tile({ icon, title, sub, to, className }: { icon: IconName; title: string; sub: string; to?: string; className?: string }) {
  const body: ReactNode = (
    <>
      <Icon name={icon} size={18} className="text-brand" />
      <span className="text-xs font-extrabold md:text-[13px]">{title}</span>
      <span className="text-[11px] text-muted md:text-xs">{sub}</span>
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
  if (!hasNumbers(canteen)) {
    return (
      <div className={cx("flex flex-col gap-1", !large && "items-center text-center")}>
        <span className={cx("font-extrabold", large ? "text-[26px] tracking-[-0.02em]" : "mt-1.5 text-lg")}>No info right now</span>
        <span className={cx("text-muted", large ? "text-sm" : "text-[13px]")}>Seat numbers are hidden until live readings return.</span>
      </div>
    );
  }
  return (
    <div className={cx("flex flex-col gap-1", !large && "items-center text-center", canteen.freshness === "stale" && "opacity-70")}>
      <span className={cx("font-extrabold", large ? "text-[26px] tracking-[-0.02em]" : "mt-1.5 text-lg")}>
        ~{canteen.free_about} seats free
      </span>
      <span className={cx("text-muted", large ? "text-sm" : "text-[13px]")}>
        Estimated {canteen.free_range[0]}–{canteen.free_range[1]} of {canteen.monitored_capacity} monitored seats
      </span>
    </div>
  );
}

function ForecastTip({ point }: { point: ForecastPoint }) {
  return (
    <div className="flex items-center gap-2.5 rounded-2xl bg-mint-soft px-3.5 py-3">
      <Icon name="trend" size={20} className="shrink-0 text-brand" />
      <div className="flex flex-col">
        <span className="text-[13px] font-extrabold">
          Likely {point.low}–{point.high}% at {formatClock(point.at)}
        </span>
        <span className="text-xs text-muted">Experimental forecast</span>
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
        <BackButton className="absolute left-4 top-[18px] h-11 w-11 rounded-[14px]" />
        <FavouriteButton canteen={canteen} className="absolute right-4 top-[18px] h-11 w-11 rounded-[14px]" />
      </div>
      <div className="relative -mt-7 flex flex-col gap-3.5 rounded-t-[28px] bg-page px-4 py-5">
        <div className="flex items-start justify-between gap-2.5">
          <div className="flex flex-col gap-1">
            <h1 className="m-0 text-[26px] font-extrabold tracking-[-0.02em]">{canteen.name}</h1>
            <LiveLine freshness={canteen.freshness} text={freshnessText(canteen.freshness, canteen.updated_at, now)} />
          </div>
          <StatusPill level={canteen.level} freshness={canteen.freshness} />
        </div>
        {online ? (
          <section
            aria-label="Seat estimate"
            className="flex flex-col items-center gap-1.5 rounded-[22px] border border-line bg-card px-4 pb-4 pt-[18px]"
          >
            <HalfGauge percent={canteen.percent} level={canteen.level} freshness={canteen.freshness} caption="seats in use (est.)" />
            <SeatHeadline canteen={canteen} />
          </section>
        ) : (
          <OfflineCard />
        )}
        {online ? <AlternativeCard canteen={canteen} /> : null}
        <div className="grid grid-cols-3 gap-2">
          <Tile
            icon="clock"
            title={isOpenNow(hours_today, now) ? "Open now" : "Closed now"}
            sub={hoursText(hours_today)}
            className="border border-line bg-card"
          />
          <Tile
            icon="store"
            title={`${canteen.shops_total} shops`}
            sub={`${canteen.shops_open} open now`}
            to={`/food?canteen=${canteen.id}`}
            className="border border-line bg-card"
          />
          {canteen.walk ? (
            <Tile
              icon="walk"
              title={`${canteen.walk.minutes} min`}
              sub={`from ${canteen.walk.from_name}`}
              className="border border-line bg-card"
            />
          ) : (
            <Tile
              icon="camera"
              title={`${canteen.zones_live} of ${canteen.zones_total} zones`}
              sub="with live data"
              className="border border-line bg-card"
            />
          )}
        </div>
        <h2 className="m-0 mt-1 text-[17px] font-extrabold">Seats by zone</h2>
        {online ? (
          <ul className="m-0 flex list-none flex-col rounded-[18px] border border-line bg-card px-3.5 py-1">
            {zones.map((z, i) => (
              <ZoneBarRow key={z.zone_id} zone={z} last={i === zones.length - 1} seats={seats.get(z.zone_id)} />
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
      className="flex min-w-0 flex-[1.2_1_420px] flex-col gap-3.5 rounded-[22px] border border-line bg-card p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="fc-title" className="m-0 text-[17px] font-extrabold">
          Next hour
        </h2>
        <span className="rounded-full bg-neutral px-[9px] py-1 text-xs font-bold text-neutral-ink">Experimental forecast</span>
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
              className="forecast-stripes w-full max-w-16 rounded-t-[10px] rounded-b"
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
          className="flex min-w-0 flex-[1_1_420px] flex-col gap-4 rounded-[26px] border border-line bg-card p-6"
        >
          <div className="flex flex-wrap items-start justify-between gap-2.5">
            <div className="flex flex-col gap-1">
              <h1 className="m-0 text-[32px] font-extrabold tracking-[-0.03em]">{canteen.name}</h1>
              <LiveLine freshness={canteen.freshness} text={freshnessText(canteen.freshness, canteen.updated_at, now)} />
            </div>
            <StatusPill level={canteen.level} freshness={canteen.freshness} size="lg" />
          </div>
          {online ? (
            <div className="flex flex-wrap items-center gap-[22px]">
              <HalfGauge percent={canteen.percent} level={canteen.level} freshness={canteen.freshness} caption="in use (est.)" />
              <SeatHeadline canteen={canteen} large />
            </div>
          ) : (
            <OfflineCard />
          )}
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
      <h2 className="m-0 mt-1 text-[22px] font-extrabold tracking-[-0.02em]">Seats by zone</h2>
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
          className="flex min-w-0 flex-[1_1_360px] flex-col gap-1 rounded-[22px] border border-line bg-card p-5"
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
