import { signOut, useConsoleOverview, type StaffRole, type StaffUser } from "@dinemate/api-client";
import { APP_NAME, cx, Icon, type IconName } from "@dinemate/ui";
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
};

function useOpenAlertCount(enabled: boolean): number {
  const overview = useConsoleOverview(enabled);
  return overview.data?.alerts.filter((a) => a.status === "open").length ?? 0;
}

function Sidebar({ user }: { user: StaffUser }) {
  const items = navFor(user);
  const openAlerts = useOpenAlertCount(MANAGERS.includes(user.role));
  const queryClient = useQueryClient();
  return (
    <aside className="box-border flex flex-[1_1_232px] flex-col gap-6 bg-side px-4 py-6 text-white">
      <div className="flex items-center gap-2.5 px-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-brand">
          <Icon name="bench" size={20} />
        </span>
        <span className="flex flex-col">
          <span className="text-[17px] font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
          <span className="text-xs text-side-muted">Staff console</span>
        </span>
      </div>
      <nav aria-label="Console" className="flex flex-col gap-1">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cx(
                "flex min-h-11 items-center gap-2.5 rounded-[10px] px-3 text-sm no-underline",
                isActive ? "bg-side-active font-bold text-white" : "font-semibold text-side-ink hover:bg-side-card hover:text-white",
              )
            }
          >
            <Icon name={item.icon} size={18} />
            <span className="flex-1">{item.label}</span>
            {item.badge === "alerts" && openAlerts > 0 ? (
              <span aria-label={`${openAlerts} open`} className="rounded-full bg-crowd-mark px-[7px] py-px text-xs font-bold text-white">
                {openAlerts}
              </span>
            ) : null}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-0.5 rounded-xl bg-side-card p-3">
        <span className="text-xs text-side-muted">Signed in as · {ROLE_LABEL[user.role]}</span>
        <span className="text-sm font-bold">{user.display_name}</span>
        <button
          type="button"
          onClick={() => {
            void signOut().then(() => queryClient.clear());
          }}
          className="mt-2 min-h-9 rounded-lg border border-side-active bg-transparent px-3 text-left text-[13px] font-semibold text-side-ink hover:bg-side-active hover:text-white"
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
        className="sr-only rounded-xl bg-brand px-4 py-3 font-bold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
      >
        Skip to content
      </a>
      <Sidebar user={user} />
      <Outlet />
    </div>
  );
}
