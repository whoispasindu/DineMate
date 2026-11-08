import { useAlertFeed, useServerNow } from "@dinemate/api-client";
import { APP_NAME, BrandMark, cx, Icon, type IconName } from "@dinemate/ui";
import { useState, type FormEvent } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useRegisterSW } from "virtual:pwa-register/react";
import { isStandalone, useIsDesktop } from "../lib/device";
import { alertsSeenAt, unreadCount, welcomeSeen } from "../lib/prefs";

interface Tab {
  to: string;
  label: string;
  webLabel: string;
  icon: IconName;
  end?: boolean;
}

const TABS: Tab[] = [
  { to: "/", label: "Home", webLabel: "Home", icon: "home", end: true },
  { to: "/canteens", label: "Canteens", webLabel: "Canteens", icon: "seat" },
  { to: "/food", label: "Food", webLabel: "Food", icon: "utensils" },
  { to: "/meals", label: "Meals", webLabel: "Meal times", icon: "clock" },
  { to: "/alerts", label: "Alerts", webLabel: "Alerts", icon: "bell" },
];

export function useUnread(): number {
  const feed = useAlertFeed();
  const seenAt = alertsSeenAt.use();
  const now = useServerNow(30_000);
  return unreadCount(feed.data, seenAt, now);
}

export function BellLink({ className, dotClassName }: { className?: string; dotClassName?: string }) {
  const unread = useUnread();
  return (
    <Link
      to="/alerts"
      aria-label={unread > 0 ? `Alerts, ${unread} new` : "Alerts"}
      className={cx("relative flex items-center justify-center", className)}
    >
      <Icon name="bell" size={20} />
      {unread > 0 ? <span className={cx("absolute rounded-full bg-notify", dotClassName)} /> : null}
    </Link>
  );
}

function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only rounded-xl bg-brand px-4 py-3 font-bold text-sand focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
    >
      Skip to content
    </a>
  );
}

function HeaderSearch() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    navigate(q.trim() ? `/food?q=${encodeURIComponent(q.trim())}` : "/food");
  };
  return (
    <form role="search" onSubmit={submit} className="relative">
      <label htmlFor="web-search" className="sr-only">
        Search food
      </label>
      <Icon name="search" size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-on-dark-faint" />
      <input
        id="web-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search canteens or food"
        className="h-[42px] w-60 max-w-full rounded-xl border border-white/10 bg-brand-mid pl-[38px] pr-3 text-sm text-sand placeholder:text-on-dark-faint"
      />
    </form>
  );
}

function TopBar() {
  const { pathname } = useLocation();
  return (
    <header className="bg-brand text-sand">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-7 gap-y-4 px-6 py-3.5">
        <Link to="/" className="flex items-center gap-2.5 text-sand no-underline">
          <BrandMark tone="sand" size={36} />
          <span className="font-display text-xl font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
        </Link>
        <nav aria-label="Main" className="flex flex-[1_1_360px] flex-wrap gap-1">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cx(
                  "inline-flex min-h-10 items-center rounded-[10px] px-3.5 text-sm no-underline",
                  isActive ? "bg-white/10 font-bold text-sand" : "font-semibold text-on-dark-faint hover:bg-white/5 hover:text-sand",
                )
              }
            >
              {tab.webLabel}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-2.5">
          {pathname === "/" ? <HeaderSearch /> : null}
          {pathname !== "/alerts" ? (
            <BellLink
              className="h-[42px] w-[42px] rounded-xl border border-white/10 text-sand hover:bg-white/5"
              dotClassName="right-[9px] top-2 h-2 w-2"
            />
          ) : null}
        </div>
      </div>
    </header>
  );
}

function TabBar() {
  return (
    <div className="sticky bottom-0 z-10 px-3 pb-[max(14px,env(safe-area-inset-bottom))] pt-2">
      <nav aria-label="Main" className="slab flex h-[68px] items-center justify-around rounded-[24px] bg-brand px-2">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              cx(
                "relative flex min-h-12 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-semibold no-underline",
                isActive ? "text-sand" : "text-on-dark-faint",
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon name={tab.icon} size={22} strokeWidth={isActive ? 2.2 : 1.8} />
                {tab.label}
                {isActive ? <span aria-hidden="true" className="absolute -bottom-1 h-[5px] w-[5px] rounded-full bg-sand" /> : null}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function UpdateToast() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW();
  if (!needRefresh) return null;
  return (
    <div role="status" className="fixed inset-x-4 bottom-24 z-30 mx-auto max-w-sm md:bottom-6">
      <button
        type="button"
        onClick={() => updateServiceWorker(true)}
        className="edge-forest flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border-0 bg-brand px-4 text-sm font-bold text-sand"
      >
        <Icon name="refresh" size={16} />
        New version — tap to refresh
      </button>
    </div>
  );
}

export function AppShell() {
  const isDesktop = useIsDesktop();
  const seen = welcomeSeen.use();
  if (!seen && !isStandalone()) return <Navigate to="/welcome" replace />;
  if (isDesktop) {
    return (
      <div className="min-h-dvh">
        <SkipLink />
        <TopBar />
        <Outlet />
        <UpdateToast />
      </div>
    );
  }
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[560px] flex-col">
      <SkipLink />
      <div className="flex flex-1 flex-col">
        <Outlet />
      </div>
      <TabBar />
      <UpdateToast />
    </div>
  );
}
