import { useConsoleOverview } from "@dinemate/api-client";
import { APP_NAME, cx, Icon, type IconName } from "@dinemate/ui";
import { NavLink, Outlet } from "react-router";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
  badge?: "alerts";
}

export const NAV: NavItem[] = [
  { to: "/", label: "Overview", icon: "grid", end: true },
  { to: "/occupancy", label: "Occupancy", icon: "pulse" },
  { to: "/alerts", label: "Alerts", icon: "bell", badge: "alerts" },
  { to: "/shops", label: "Shops & menus", icon: "store" },
  { to: "/schedules", label: "Meal schedules", icon: "calendar" },
  { to: "/devices", label: "Devices", icon: "camera" },
  { to: "/safety", label: "Safety", icon: "shield" },
  { to: "/config", label: "Thresholds & config", icon: "sliders" },
];

function useOpenAlertCount(): number {
  const overview = useConsoleOverview();
  return overview.data?.alerts.filter((a) => a.status === "open").length ?? 0;
}

function Sidebar() {
  const openAlerts = useOpenAlertCount();
  return (
    <aside className="box-border flex flex-[1_1_232px] flex-col gap-6 bg-side px-4 py-6 text-white">
      <div className="flex items-center gap-2.5 px-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-brand">
          <Icon name="bench" size={20} />
        </span>
        <span className="flex flex-col">
          <span className="text-[17px] font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
          <span className="text-xs text-side-muted">Admin console</span>
        </span>
      </div>
      <nav aria-label="Admin" className="flex flex-col gap-1">
        {NAV.map((item) => (
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
        <span className="text-xs text-side-muted">Signed in as</span>
        <span className="text-sm font-bold">Campus administrator</span>
      </div>
    </aside>
  );
}

export function ConsoleShell() {
  return (
    <div className="flex min-h-dvh flex-wrap bg-page">
      <a
        href="#main"
        className="sr-only rounded-xl bg-brand px-4 py-3 font-bold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
      >
        Skip to content
      </a>
      <Sidebar />
      <Outlet />
    </div>
  );
}
