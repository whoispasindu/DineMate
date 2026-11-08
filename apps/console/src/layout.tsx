import { signOut, useConsoleOverview, type StaffRole, type StaffUser } from "@dinemate/api-client";
import { APP_NAME, BrandMark, cx, Icon, type IconName } from "@dinemate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
  badge?: "alerts";
  roles: StaffRole[];
}

const MANAGERS: StaffRole[] = ["campus_admin", "canteen_manager"];

export const NAV: NavItem[] = [
  { to: "/", label: "Overview", icon: "grid", end: true, roles: MANAGERS },
  { to: "/occupancy", label: "Occupancy", icon: "pulse", roles: MANAGERS },
  { to: "/seats", label: "Seats", icon: "bench", roles: MANAGERS },
  { to: "/alerts", label: "Alerts", icon: "bell", badge: "alerts", roles: MANAGERS },
  { to: "/shops", label: "Shops & menus", icon: "store", roles: [...MANAGERS, "shop_manager"] },
  { to: "/schedules", label: "Meal schedules", icon: "calendar", roles: MANAGERS },
  { to: "/zones", label: "Zones", icon: "seat", roles: MANAGERS },
  { to: "/devices", label: "Devices", icon: "camera", roles: ["campus_admin"] },
  { to: "/safety", label: "Safety", icon: "shield", roles: ["campus_admin", "safety_officer"] },
  { to: "/config", label: "Thresholds & config", icon: "sliders", roles: MANAGERS },
];

export function navFor(user: StaffUser): NavItem[] {
  return NAV.filter((n) => n.roles.includes(user.role));
}

const ROLE_LABEL: Record<StaffRole, string> = {
  campus_admin: "Campus admin",
  canteen_manager: "Canteen manager",
  shop_manager: "Shop manager",
  safety_officer: "Safety officer",
  owner: "Business owner",
  venue_manager: "Venue manager",
};

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

function useOpenAlertCount(enabled: boolean): number {
  const overview = useConsoleOverview(enabled);
  return overview.data?.alerts.filter((a) => a.status === "open").length ?? 0;
}

function Sidebar({ user }: { user: StaffUser }) {
  const items = navFor(user);
  const openAlerts = useOpenAlertCount(MANAGERS.includes(user.role));
  const queryClient = useQueryClient();
  return (
    <aside className="box-border flex flex-[1_1_248px] flex-col gap-6 bg-side px-[18px] py-7 text-sand min-[820px]:sticky min-[820px]:top-0 min-[820px]:h-dvh min-[820px]:self-start">
      <div className="flex items-center gap-2.5 px-2">
        <BrandMark tone="sand" size={34} />
        <span className="flex flex-col">
          <span className="font-display text-[19px] font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
          <span className="text-xs text-side-muted">Staff console</span>
        </span>
      </div>
      <nav aria-label="Console" className="scrollbar-none flex min-h-0 flex-col gap-1 overflow-y-auto">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cx(
                "group flex min-h-[42px] items-center gap-3 rounded-xl px-3.5 text-sm no-underline",
                isActive ? "is-active bg-white/10 font-bold text-sand" : "font-semibold text-side-muted hover:bg-white/5 hover:text-sand",
              )
            }
          >
            <Icon name={item.icon} size={19} />
            <span className="flex-1">{item.label}</span>
            <span aria-hidden="true" className="hidden h-1.5 w-1.5 rounded-full bg-sand group-[.is-active]:block" />
            {item.badge === "alerts" && openAlerts > 0 ? (
              <span
                aria-label={`${openAlerts} open`}
                className="rounded-full bg-crowd-mark px-[7px] py-px font-mono text-xs font-bold text-card"
              >
                {openAlerts}
              </span>
            ) : null}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-2 rounded-2xl bg-white/[0.08] p-3.5">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-[11px] bg-sand font-display text-[13px] font-extrabold text-brand"
          >
            {initials(user.display_name)}
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-[13px] font-bold">{user.display_name}</span>
            <span className="text-xs text-side-muted">{ROLE_LABEL[user.role]}</span>
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

export function ConsoleShell({ user }: { user: StaffUser }) {
  return (
    <div className="flex min-h-dvh flex-wrap bg-page">
      <a
        href="#main"
        className="sr-only rounded-xl bg-brand px-4 py-3 font-bold text-sand focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
      >
        Skip to content
      </a>
      <Sidebar user={user} />
      <Outlet />
    </div>
  );
}
