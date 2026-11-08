import { serverNow, useAlertFeed, type Notice, type NoticeKind } from "@dinemate/api-client";
import { APP_NAME, cx, formatClock, formatClock24, Icon } from "@dinemate/ui";
import { useId, useState } from "react";
import { Link } from "react-router";
import { FilterChips, Loading, MessageCard, SafetyBanner, SafetyUnknown, Segmented, Skeleton } from "../components/common";
import { useSafety } from "../components/safety";
import { useIsDesktop } from "../lib/device";
import { alertsSeenAt, notificationPrefs, type NotificationPrefs } from "../lib/prefs";
import { NOTICE_LOOK } from "../lib/present";

type Filter = "all" | "safety" | "crowding" | "shops" | "system";

const FILTER_KINDS: Record<Exclude<Filter, "all" | "safety">, NoticeKind[]> = {
  crowding: ["crowding"],
  shops: ["sold_out", "shop_closing", "meal_starting"],
  system: ["data_unavailable"],
};

const MOBILE_FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "safety", label: "Safety" },
  { value: "crowding", label: "Crowding" },
  { value: "shops", label: "Shops" },
];

const WEB_FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "safety", label: "Safety" },
  { value: "crowding", label: "Crowding" },
  { value: "shops", label: "Shops & meals" },
  { value: "system", label: "System" },
];

const PREFS: { key: keyof NotificationPrefs | "safety"; title: string; sub: string }[] = [
  { key: "safety", title: "Safety notices", sub: "Always on" },
  { key: "crowding", title: "Crowding", sub: "At most once per 15 min" },
  { key: "meals", title: "Meal times", sub: "10 min before a meal starts" },
  { key: "closing", title: "Shops closing soon", sub: "Favourite shops only" },
  { key: "soldOut", title: "Sold-out items", sub: "From shops you view" },
];

function visibleNotices(notices: Notice[], filter: Filter): Notice[] {
  if (filter === "all") return notices;
  if (filter === "safety") return [];
  return notices.filter((n) => FILTER_KINDS[filter].includes(n.kind));
}

function Preferences() {
  const prefs = notificationPrefs.use();
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {PREFS.map((p, i) => {
        const locked = p.key === "safety";
        const checked = locked ? true : prefs[p.key as keyof NotificationPrefs];
        return (
          <li key={p.key} className={cx(i < PREFS.length - 1 && "border-b border-line-soft")}>
            <label className="flex min-h-[52px] items-center justify-between gap-2.5">
              <span className="flex flex-col">
                <span className="text-sm font-bold">{p.title}</span>
                <span className="text-xs text-muted">{p.sub}</span>
              </span>
              <input
                type="checkbox"
                checked={checked}
                disabled={locked}
                onChange={(e) => {
                  const value = e.target.checked;
                  notificationPrefs.set((prev) => ({ ...prev, [p.key]: value }));
                }}
                className="h-5 w-5 accent-brand"
              />
            </label>
          </li>
        );
      })}
    </ul>
  );
}

function NoticeRow({ notice, layout, last }: { notice: Notice; layout: "mobile" | "web"; last: boolean }) {
  const look = NOTICE_LOOK[notice.kind];
  const web = layout === "web";
  return (
    <li className={cx("flex", web ? "gap-3.5 py-4" : "gap-3 py-3", !last && "border-b border-line-soft")}>
      <span
        className={cx("flex shrink-0 items-center justify-center", web ? "h-11 w-11 rounded-[14px]" : "h-10 w-10 rounded-xl", look.tile)}
      >
        <Icon name={look.icon} size={web ? 20 : 19} strokeWidth={2.2} />
      </span>
      <div className={cx("flex flex-1 flex-col", web ? "gap-1" : "gap-0.5")}>
        <div className="flex justify-between gap-2.5">
          <span className={cx("font-bold", web ? "text-base" : "text-[15px]")}>{notice.title}</span>
          <span className={cx("whitespace-nowrap text-muted", web ? "text-[13px]" : "text-xs")}>
            {web ? formatClock(notice.at) : formatClock24(notice.at)}
          </span>
        </div>
        <span className={cx("leading-snug text-muted", web ? "text-sm" : "text-[13px]")}>{notice.body}</span>
        {web && notice.related_canteen ? (
          <Link
            to={`/canteens/${notice.related_canteen.id}`}
            className="mt-0.5 self-start text-[13px] font-bold text-brand no-underline hover:text-brand-dark"
          >
            See {notice.related_canteen.name}
          </Link>
        ) : null}
      </div>
    </li>
  );
}

export function AlertsScreen() {
  const isDesktop = useIsDesktop();
  const feed = useAlertFeed();
  const [filter, setFilter] = useState<Filter>("all");
  const [showPrefs, setShowPrefs] = useState(false);
  const panelId = useId();
  const prefsId = useId();
  const data = feed.data;
  const showSafety = filter === "all" || filter === "safety";
  const safety = useSafety();
  const events = showSafety ? safety.events : [];
  const notices = data ? visibleNotices(data.notices, filter) : [];
  const markAllRead = () => alertsSeenAt.set(new Date(serverNow()).toISOString());

  const safetyBlock = (
    <>
      {showSafety && safety.unknown ? <SafetyUnknown /> : null}
      {events.map((event) => (
        <SafetyBanner key={event.id} event={event} layout={isDesktop ? "web" : "mobile"} />
      ))}
    </>
  );
  const empty = data && events.length === 0 && notices.length === 0;
  const loading = !data && !feed.isError;

  if (isDesktop) {
    return (
      <main id="main" className="mx-auto flex max-w-[1200px] flex-col gap-5 px-6 pb-10 pt-7">
        <div className="flex flex-wrap items-end justify-between gap-3.5">
          <div className="flex flex-col gap-1">
            <h1 className="m-0 font-display text-[44px] font-extrabold tracking-[-0.04em]">Alerts</h1>
            <span className="text-[15px] text-muted">Safety notices are kept separate from everyday updates.</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={markAllRead}
              className="min-h-10 rounded-xl border-0 bg-transparent px-3 text-sm font-bold text-brand hover:bg-mint"
            >
              Mark all read
            </button>
            <Segmented label="Filter alerts" options={WEB_FILTERS} value={filter} onChange={setFilter} panelId={panelId} />
          </div>
        </div>
        <div className="flex flex-wrap items-start gap-5">
          <div id={panelId} role="tabpanel" className="flex min-w-0 flex-[2_1_560px] flex-col gap-4">
            {safetyBlock}
            {loading ? (
              <Loading label="Loading alerts">
                <Skeleton className="h-[320px] rounded-[22px]" />
              </Loading>
            ) : null}
            {empty ? <MessageCard icon="checkCircle" art="no-alerts" title="No alerts today" /> : null}
            {notices.length > 0 ? (
              <section aria-labelledby="today-title" className="raised flex flex-col rounded-[22px] border border-line bg-card px-5 py-2">
                <h2 id="today-title" className="mb-1 mt-3 font-sans text-[13px] font-semibold tracking-normal text-muted">
                  Today
                </h2>
                <ul className="m-0 flex list-none flex-col p-0">
                  {notices.map((n, i) => (
                    <NoticeRow key={n.id} notice={n} layout="web" last={i === notices.length - 1} />
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
          <aside
            aria-labelledby="prefs-title"
            className="flex min-w-0 flex-[1_1_300px] flex-col gap-1.5 rounded-[22px] border border-line bg-card p-5"
          >
            <h2 id="prefs-title" className="m-0 mb-2 text-xl font-semibold">
              Notify me about
            </h2>
            <Preferences />
            <p className="m-0 mt-2.5 text-xs leading-normal text-muted">
              {APP_NAME} is a supplementary display. In a real emergency, follow official alarms and campus staff.
            </p>
          </aside>
        </div>
      </main>
    );
  }

  return (
    <>
      <header className="flex flex-col gap-3 px-4 pb-2.5 pt-[18px]">
        <div className="flex items-center justify-between">
          <h1 className="m-0 font-display text-[34px] font-extrabold tracking-[-0.04em]">Alerts</h1>
          <button
            type="button"
            onClick={markAllRead}
            className="min-h-10 rounded-xl border-0 bg-transparent px-3 text-sm font-bold text-brand"
          >
            Mark all read
          </button>
        </div>
        <FilterChips label="Filter alerts" options={MOBILE_FILTERS} value={filter} onChange={setFilter} />
      </header>
      <main id="main" className="flex flex-1 flex-col gap-3 px-4 pb-4 pt-1">
        {showSafety && (events.length > 0 || feed.isError) ? (
          <>
            <h2 className="m-0 font-sans text-[13px] font-semibold tracking-normal text-muted">Safety</h2>
            {safetyBlock}
          </>
        ) : null}
        {loading ? (
          <Loading label="Loading alerts">
            <Skeleton className="h-[300px] rounded-[20px]" />
          </Loading>
        ) : null}
        {empty ? <MessageCard icon="checkCircle" art="no-alerts" title="No alerts today" /> : null}
        {notices.length > 0 ? (
          <>
            <h2 className="m-0 mt-1 font-sans text-[13px] font-semibold tracking-normal text-muted">Today</h2>
            <ul className="m-0 flex list-none flex-col px-1.5">
              {notices.map((n, i) => (
                <NoticeRow key={n.id} notice={n} layout="mobile" last={i === notices.length - 1} />
              ))}
            </ul>
          </>
        ) : null}
        <button
          type="button"
          aria-expanded={showPrefs}
          aria-controls={prefsId}
          onClick={() => setShowPrefs((v) => !v)}
          className="flex min-h-[52px] items-center justify-between rounded-2xl border border-line bg-card px-3.5 text-sm font-bold text-ink"
        >
          Notification settings
          <Icon name={showPrefs ? "chevronDown" : "chevronRight"} size={18} strokeWidth={2.2} />
        </button>
        <div id={prefsId} hidden={!showPrefs} className="rounded-2xl border border-line bg-card px-3.5">
          <Preferences />
        </div>
      </main>
    </>
  );
}
