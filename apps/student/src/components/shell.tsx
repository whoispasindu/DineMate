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
  activeIcon?: IconName;
  end?: boolean;
}

const TABS: Tab[] = [
  { to: "/", label: "Home", webLabel: "Home", icon: "home", activeIcon: "homeSolid", end: true },
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
      className={cx("relative flex items-center justify-center text-ink", className)}
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
      className="sr-only rounded-xl bg-brand px-4 py-3 font-bold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
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
      <Icon name="search" size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input
        id="web-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search canteens or food"
        className="h-[42px] w-60 max-w-full rounded-xl border border-line bg-[#F7FAF7] pl-[38px] pr-3 text-sm placeholder:text-muted"
      />
    </form>
  );
}

function TopBar() {
  const { pathname } = useLocation();
  return (
    <header className="border-b border-line bg-card">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-7 gap-y-4 px-6 py-3.5">
        <Link to="/" className="flex items-center gap-2.5 text-ink no-underline">
          <BrandMark />
          <span className="text-lg font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
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
                  isActive ? "bg-mint font-extrabold text-brand-dark" : "font-semibold text-ink-2 hover:bg-page",
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
            <BellLink className="h-[42px] w-[42px] rounded-xl border border-line hover:bg-page" dotClassName="right-[9px] top-2 h-2 w-2" />
          ) : null}
        </div>
      </div>
    </header>
  );
}

function TabBar() {
  return (
    <nav
      aria-label="Main"
      className="sticky bottom-0 z-10 flex justify-around border-t border-line bg-card px-2 pb-[max(20px,env(safe-area-inset-bottom))] pt-2"
    >
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cx(
              "flex min-h-12 flex-1 flex-col items-center justify-center gap-[3px] text-[11px] no-underline",
              isActive ? "font-extrabold text-brand" : "font-semibold text-muted",
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon name={isActive && tab.activeIcon ? tab.activeIcon : tab.icon} size={22} strokeWidth={isActive ? 2.4 : 2} />
              {tab.label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
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
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border-0 bg-brand-dark px-4 text-sm font-bold text-white shadow-lg"
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
