import { useAlertFeed, useServerNow, useStudentSummary, type StudentSummary } from "@dinemate/api-client";
import {
  BrandMark,
  FoodArt,
  formatAgo,
  formatClock,
  formatDayStamp,
  greeting,
  Icon,
  LiveLine,
  SampleBadge,
  shopPhotoFor,
} from "@dinemate/ui";
import type { UseQueryResult } from "@tanstack/react-query";
import { Link } from "react-router";
import { BestSpotMobile, BestSpotWeb, BusyTimesChart, CanteenCard, CanteenRow, NoBestSpot } from "../components/canteen";
import { Footnote, Loading, MessageCard, OfflineCard, ShopStatusText, Skeleton } from "../components/common";
import { MealCountdownCard, MealPill } from "../components/meal";
import { SafetySlot } from "../components/safety";
import { BellLink } from "../components/shell";
import { useIsDesktop, useOnline } from "../lib/device";
import { NOTICE_LOOK } from "../lib/present";

type Summary = UseQueryResult<StudentSummary>;

function latestUpdate(data: StudentSummary): string | null {
  const live = data.canteens.filter((c) => c.freshness === "live" && c.updated_at).map((c) => Date.parse(c.updated_at ?? ""));
  return live.length > 0 ? new Date(Math.max(...live)).toISOString() : null;
}

function bestCanteen(data: StudentSummary) {
  return data.canteens.find((c) => c.id === data.best?.canteen_id) ?? null;
}

export function HomeScreen() {
  const isDesktop = useIsDesktop();
  const summary = useStudentSummary();
  const now = useServerNow(1000);
  const online = useOnline();
  return isDesktop ? <HomeWeb summary={summary} now={now} online={online} /> : <HomeMobile summary={summary} now={now} online={online} />;
}

interface HomeProps {
  summary: Summary;
  now: number;
  online: boolean;
}

function HomeMobile({ summary, now, online }: HomeProps) {
  const data = summary.data;
  const best = data ? bestCanteen(data) : null;
  return (
    <>
      <header className="flex items-center justify-between px-[22px] pb-1 pt-4">
        <div className="flex items-center gap-2.5">
          <BrandMark size={30} />
          <span className="text-[13px] font-medium text-muted">{formatDayStamp(now)}</span>
        </div>
        <BellLink
          className="h-10 w-10 rounded-[14px] border border-line bg-card text-ink"
          dotClassName="right-2.5 top-[9px] h-[7px] w-[7px]"
        />
      </header>
      <main id="main" className="flex flex-1 flex-col gap-4 px-4 pb-4 pt-3">
        <h1 className="m-0 px-1.5 font-display text-[34px] font-extrabold leading-[1.02] tracking-[-0.04em]">
          {greeting(now)}.
          <br />
          <span className="font-semibold text-faint">Where will you sit?</span>
        </h1>
        <SafetySlot layout="mobile" />
        {!online ? (
          <>
            <OfflineCard />
            <MealPill />
          </>
        ) : !data ? (
          summary.isError ? (
            <MessageCard icon="wifiOff" art="offline" title="Couldn't load seat info" body="Retrying automatically…" />
          ) : (
            <Loading label="Loading seat info">
              <Skeleton className="h-[290px] rounded-[22px]" />
              <Skeleton className="h-[86px]" />
              <Skeleton className="h-[86px]" />
            </Loading>
          )
        ) : (
          <>
            {best ? <BestSpotMobile canteen={best} /> : <NoBestSpot anyLive={data.canteens.some((c) => c.freshness === "live")} />}
            <MealPill />
            <div className="mt-1 flex items-center justify-between px-1.5">
              <h2 className="m-0 text-[22px] font-semibold">All canteens</h2>
              {data.canteens.some((c) => c.is_sample) ? <SampleBadge /> : null}
            </div>
            <ul className="m-0 flex list-none flex-col px-1.5">
              {data.canteens.map((c, i) => (
                <li key={c.id} className={i > 0 ? "border-t border-line" : undefined}>
                  <CanteenRow canteen={c} now={now} />
                </li>
              ))}
            </ul>
          </>
        )}
        <Footnote>Seat counts are estimates. No video is stored.</Footnote>
      </main>
    </>
  );
}

function HomeWeb({ summary, now, online }: HomeProps) {
  const data = summary.data;
  const updated = data ? latestUpdate(data) : null;
  const best = data ? bestCanteen(data) : null;
  return (
    <main id="main" className="mx-auto flex max-w-[1200px] flex-col gap-6 px-6 pb-10 pt-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 font-display text-[44px] font-extrabold leading-none tracking-[-0.04em]">{greeting(now)}.</h1>
          <span className="text-base text-muted">Here is where you can sit right now.</span>
        </div>
        <div className="flex items-center gap-2.5">
          {online && updated ? <LiveLine text={`Live · updated ${formatAgo(updated, now)}`} /> : null}
          {data?.canteens.some((c) => c.is_sample) ? <SampleBadge /> : null}
        </div>
      </div>
      <SafetySlot layout="web" />
      {!online ? <OfflineCard /> : null}
      <div className="flex flex-wrap gap-5">
        {!online ? null : !data ? (
          <Skeleton className="min-h-[278px] flex-[2_1_560px] rounded-[26px]" />
        ) : best ? (
          <BestSpotWeb canteen={best} />
        ) : (
          <div className="flex-[2_1_560px]">
            <NoBestSpot anyLive={data.canteens.some((c) => c.freshness === "live")} />
          </div>
        )}
        <MealCountdownCard className="min-w-0 flex-[1_1_300px]" />
      </div>
      {online ? (
        <>
          <div className="flex items-center justify-between">
            <h2 className="m-0 text-[26px] font-semibold">All canteens</h2>
            <Link to="/canteens" className="inline-flex items-center gap-1 text-sm font-bold text-brand no-underline hover:text-brand-dark">
              Compare all
              <Icon name="arrowRight" size={16} strokeWidth={2.4} />
            </Link>
          </div>
          {data ? (
            <div className="flex flex-wrap gap-5">
              {data.canteens.map((c) => (
                <CanteenCard key={c.id} canteen={c} now={now} />
              ))}
            </div>
          ) : summary.isError ? (
            <MessageCard icon="wifiOff" art="offline" title="Couldn't load seat info" body="Retrying automatically…" />
          ) : (
            <Loading label="Loading canteens">
              <div className="flex flex-wrap gap-5">
                <Skeleton className="h-[260px] flex-[1_1_300px] rounded-[22px]" />
                <Skeleton className="h-[260px] flex-[1_1_300px] rounded-[22px]" />
                <Skeleton className="h-[260px] flex-[1_1_300px] rounded-[22px]" />
              </div>
            </Loading>
          )}
        </>
      ) : null}
      <div className="flex flex-wrap gap-5">
        {online && data?.busy_today ? (
          <BusyTimesChart title={`Busy times today · ${data.busy_today.canteen_name}`} points={data.busy_today.points} />
        ) : null}
        {data ? <ShopsNow shops={data.shops_now} /> : null}
        <LatestAlerts />
      </div>
      <Footnote className="text-[13px]">Seat counts are estimates from privacy-preserving sensors. No video is stored.</Footnote>
    </main>
  );
}

function ShopsNow({ shops }: { shops: StudentSummary["shops_now"] }) {
  return (
    <section
      aria-labelledby="shops-now-title"
      className="raised flex min-w-0 flex-[1_1_300px] flex-col gap-1 rounded-[22px] border border-line bg-card p-5"
    >
      <div className="mb-1.5 flex items-center justify-between">
        <h2 id="shops-now-title" className="m-0 text-xl font-semibold">
          Shops
        </h2>
        <Link to="/food" className="text-[13px] font-bold text-brand no-underline hover:text-brand-dark">
          All food
        </Link>
      </div>
      <ul className="m-0 flex list-none flex-col p-0">
        {shops.map((shop, i) => (
          <li key={shop.id} className={i < shops.length - 1 ? "border-b border-line-soft" : undefined}>
            <Link
              to={`/food?canteen=${shop.canteen_id}&shop=${shop.id}`}
              className="flex items-center justify-between gap-2 py-[9px] text-ink no-underline hover:text-brand-dark"
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <FoodArt photo={shopPhotoFor(shop.id, shop.kind)} className="h-9 w-9 shrink-0 rounded-[10px]" />
                <span className="flex flex-col">
                  <span className="text-sm font-bold">{shop.name}</span>
                  <span className="text-xs text-muted">{shop.canteen_name}</span>
                </span>
              </span>
              <ShopStatusText status={shop.status} className="text-right" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function LatestAlerts() {
  const feed = useAlertFeed();
  const notices = feed.data?.notices.slice(0, 3) ?? [];
  return (
    <section
      aria-labelledby="latest-title"
      className="raised flex min-w-0 flex-[1_1_300px] flex-col gap-2.5 rounded-[22px] border border-line bg-card p-5"
    >
      <div className="flex items-center justify-between">
        <h2 id="latest-title" className="m-0 text-xl font-semibold">
          Latest alerts
        </h2>
        <Link to="/alerts" className="text-[13px] font-bold text-brand no-underline hover:text-brand-dark">
          View all
        </Link>
      </div>
      {feed.data && notices.length === 0 ? <span className="text-sm text-muted">No alerts today</span> : null}
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {notices.map((n) => {
          const look = NOTICE_LOOK[n.kind];
          return (
            <li key={n.id} className="flex gap-3">
              <span className={`flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-xl ${look.tile}`}>
                <Icon name={look.icon} size={18} strokeWidth={2.2} />
              </span>
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-bold">{n.title}</span>
                <span className="text-xs text-muted">
                  {formatClock(n.at)} · {n.context}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
