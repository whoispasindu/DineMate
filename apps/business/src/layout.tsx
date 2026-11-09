import { signOut, type StaffUser } from "@dinemate/api-client";
import { APP_NAME, BrandMark, cx, Icon, type IconName } from "@dinemate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router";
import { useIsWide, useVenue } from "./venue";

export interface NavItem {
  to: string;
  label: string;
  short: string;
  icon: IconName;
  end?: boolean;
  owner?: boolean;
  phone?: boolean;
}

export const NAV: NavItem[] = [
  { to: "/", label: "Live floor", short: "Floor", icon: "grid", end: true, phone: true },
  { to: "/customers", label: "Customers", short: "Customers", icon: "users", phone: true },
  { to: "/staff", label: "Staff", short: "Staff", icon: "badge", owner: true },
  { to: "/sales", label: "Sales", short: "Sales", icon: "coffee", phone: true },
  { to: "/reports", label: "Reports", short: "Reports", icon: "chart", phone: true },
  { to: "/cameras", label: "Cameras", short: "Cameras", icon: "camera" },
  { to: "/privacy", label: "Privacy & consent", short: "Privacy", icon: "lock", owner: true },
  { to: "/settings", label: "Settings", short: "Settings", icon: "sliders", phone: true },
];

const ROLE_LABEL: Record<string, string> = { owner: "Owner", venue_manager: "Venue manager" };

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}

function VenueSwitcher({ dark }: { dark?: boolean }) {
  const { venues, venue, select } = useVenue();
  if (!venue) return null;
  if (venues.length < 2) {
    return (
      <div className={cx("flex flex-col rounded-[14px] px-3 py-2.5", dark ? "bg-white/[0.08]" : "")}>
        <span className="text-sm font-bold">{venue.name}</span>
        <span className={cx("text-xs", dark ? "text-side-muted" : "text-muted")}>
          {venue.zones.map((z) => z.name).join(" · ")} · {venue.tables} tables
        </span>
      </div>
    );
  }
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="sr-only">Venue</span>
      <select
        value={venue.id}
        onChange={(e) => select(e.target.value)}
        className="min-h-10 rounded-[12px] border border-white/15 bg-white/[0.08] px-3 text-sm font-bold text-side-ink"
      >
        {venues.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function Sidebar({ user }: { user: StaffUser }) {
  const queryClient = useQueryClient();
  return (
    <aside className="sticky top-0 box-border flex h-dvh print:hidden w-[248px] shrink-0 flex-col gap-5 bg-side px-[18px] py-6 text-side-ink">
      <div className="flex items-center gap-2.5 px-2">
        <BrandMark tone="sand" size={34} />
        <span className="flex flex-col">
          <span className="font-display text-[19px] font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
          <span className="text-xs font-semibold text-purple-soft">Business</span>
        </span>
      </div>
      <VenueSwitcher dark />
      <nav aria-label="Business" className="scrollbar-none flex min-h-0 flex-col gap-1 overflow-y-auto">
        {NAV.filter((item) => !item.owner || user.role === "owner").map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cx(
                "relative flex min-h-[42px] items-center gap-3 rounded-xl px-3.5 text-sm no-underline",
                isActive ? "bg-white/10 font-bold text-side-ink" : "font-semibold text-side-muted hover:bg-white/5 hover:text-side-ink",
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive ? <span aria-hidden="true" className="absolute -left-[18px] top-2.5 bottom-2.5 w-1 rounded-r bg-purple" /> : null}
                <Icon name={item.icon} size={19} />
                <span className="flex-1">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-2 rounded-2xl bg-white/[0.08] p-3.5">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-[11px] bg-purple font-display text-[13px] font-extrabold text-white"
          >
            {initials(user.display_name)}
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-[13px] font-bold">{user.display_name}</span>
            <span className="text-xs text-side-muted">{ROLE_LABEL[user.role] ?? user.role}</span>
          </span>
        </div>
        <button
          type="button"
          onClick={() => {
            void signOut().then(() => queryClient.clear());
          }}
          className="min-h-9 rounded-lg border border-white/15 bg-transparent px-3 text-left text-[13px] font-semibold text-side-ink hover:bg-white/10"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}

function PhoneTop() {
  const { venue } = useVenue();
  return (
    <header className="flex items-center justify-between gap-3 px-4 pt-4 print:hidden">
      <div className="flex items-center gap-2.5">
        <BrandMark size={32} />
        <div className="flex flex-col">
          <span className="text-[15px] font-bold">{venue?.name ?? APP_NAME}</span>
          <span className="text-xs text-muted">{venue?.zones.map((z) => z.name).join(" · ")}</span>
        </div>
      </div>
    </header>
  );
}

function PhoneTabs() {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 px-3 print:hidden pb-[max(14px,env(safe-area-inset-bottom))] pt-2">
      <nav aria-label="Business" className="slab flex h-[66px] items-center justify-around rounded-[22px] bg-brand">
        {NAV.filter((n) => n.phone).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cx(
                "relative flex min-h-12 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-semibold no-underline",
                isActive ? "text-on-dark" : "text-on-dark-faint",
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon name={item.icon} size={22} strokeWidth={isActive ? 2.2 : 1.8} />
                {item.short}
                {isActive ? <span aria-hidden="true" className="absolute -bottom-1 h-[5px] w-[5px] rounded-full bg-purple" /> : null}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

export function BusinessShell({ user }: { user: StaffUser }) {
  const wide = useIsWide();
  return (
    <div className="flex min-h-dvh bg-page">
      <a
        href="#main"
        className="sr-only rounded-xl bg-brand px-4 py-3 font-bold text-on-dark focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
      >
        Skip to content
      </a>
      {wide ? <Sidebar user={user} /> : null}
      <div className="flex min-w-0 flex-1 flex-col">
        {wide ? null : <PhoneTop />}
        <Outlet />
      </div>
      {wide ? null : <PhoneTabs />}
    </div>
  );
}
