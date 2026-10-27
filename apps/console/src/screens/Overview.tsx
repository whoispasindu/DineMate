import {
  useAcknowledgeAlert,
  useConsoleOverview,
  useMealStatus,
  useServerNow,
  type ConsoleOverview,
  type ConsoleZone,
  type DeviceHealth,
  type OccupancyPoint,
  type StaffAlert,
} from "@dinemate/api-client";
import {
  cx,
  formatAgo,
  formatClock,
  formatClock24,
  formatCountdown,
  formatDateLine,
  formatMinutes,
  HazardFrame,
  Icon,
  LEVELS,
  SampleBadge,
  SimulationLabel,
  type IconName,
} from "@dinemate/ui";
import { useEffect, type ReactNode } from "react";
import { Link } from "react-router";

const PERIOD_LABEL = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner" } as const;

const CHIP = "inline-flex items-center gap-[5px] whitespace-nowrap rounded-full px-[9px] py-1 text-xs font-semibold";

const ZONE_ICON: Record<string, IconName> = {
  crowded: "warning",
  near_capacity: "ban",
  busy: "triangle",
  normal: "checkCircle",
  unknown: "question",
};

function zoneChip(zone: ConsoleZone): { label: string; className: string; icon: IconName } {
  if (zone.freshness === "stale") return { label: "Stale", className: LEVELS.unknown.pill, icon: "question" };
  if (zone.freshness === "unavailable") return { label: "No live data", className: LEVELS.unknown.pill, icon: "question" };
  return { label: LEVELS[zone.level].label, className: LEVELS[zone.level].pill, icon: ZONE_ICON[zone.level] ?? "question" };
}

function Card({ children, className, labelledBy }: { children: ReactNode; className?: string; labelledBy?: string }) {
  return (
    <section
      aria-labelledby={labelledBy}
      className={cx("flex min-w-0 flex-col rounded-2xl border border-line bg-card px-5 py-[18px]", className)}
    >
      {children}
    </section>
  );
}

function Kpi({ title, value, suffix, sub, tone }: { title: string; value: string; suffix?: string; sub: string; tone?: "alert" }) {
  return (
    <div className="flex flex-[1_1_200px] flex-col gap-1.5 rounded-2xl border border-line bg-card px-[18px] py-4">
      <span className="text-[13px] font-semibold text-muted">{title}</span>
      <span className={cx("text-[30px] font-extrabold tracking-[-0.02em]", tone === "alert" && "text-crowd")}>
        {value}
        {suffix ? <span className="text-base font-semibold text-muted"> {suffix}</span> : null}
      </span>
      <span className="text-xs text-muted">{sub}</span>
    </div>
  );
}

function kpis(data: ConsoleOverview) {
  const live = data.zones.filter((z) => z.freshness === "live" && z.occupied !== null && z.occupied_range !== null);
  const free = live.reduce((s, z) => s + z.capacity - (z.occupied ?? 0), 0);
  const low = live.reduce((s, z) => s + z.capacity - (z.occupied_range?.[1] ?? 0), 0);
  const high = live.reduce((s, z) => s + z.capacity - (z.occupied_range?.[0] ?? 0), 0);
  const crowding = data.alerts.filter((a) => a.type === "crowding" && a.status !== "resolved");
  const attention = data.devices.filter((d) => d.status !== "ok");
  return {
    live: live.length,
    stale: data.zones.filter((z) => z.freshness === "stale").length,
    unavailable: data.zones.filter((z) => z.freshness === "unavailable").length,
    free,
    low,
    high,
    capacity: live.reduce((s, z) => s + z.capacity, 0),
    crowding: crowding.length,
    awaiting: crowding.filter((a) => a.status === "open").length,
    attention: attention.length,
    offline: attention.filter((d) => d.status === "offline").length,
    notReporting: attention.filter((d) => d.status === "not_reporting").length,
  };
}

function MealChip({ now }: { now: number }) {
  const meal = useMealStatus();
  const data = meal.data;
  const target = data?.current?.ends ?? data?.next?.starts ?? null;
  const remaining = target ? Date.parse(target) - now : null;
  const expired = remaining !== null && remaining <= 0;
  const { refetch } = meal;
  useEffect(() => {
    if (expired) void refetch();
  }, [expired, refetch]);
  if (!data || remaining === null) return null;
  const focus = data.current ?? data.next;
  if (!focus) return null;
  return (
    <span className="inline-flex min-h-10 items-center gap-2 rounded-[10px] bg-side px-3.5 text-[13px] font-semibold text-white">
      <span className="h-2 w-2 rounded-full bg-live-dot" />
      {PERIOD_LABEL[focus.period]} · {data.current ? "ends" : "starts"} in{" "}
      <span className="tabular font-mono">{formatCountdown(Math.max(0, remaining))}</span>
    </span>
  );
}

function ZoneTable({ zones, now }: { zones: ConsoleZone[]; now: number }) {
  return (
    <Card labelledBy="occ-title" className="flex-[2_1_620px] gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 id="occ-title" className="m-0 text-[17px] font-extrabold">
          Live occupancy by zone
        </h2>
        <span className="text-xs text-muted">Estimates · ranges are 80% intervals</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              {["Zone", "Seats", "Occupied (est.)", "Load", "Status", "Updated"].map((h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={cx(
                    "border-b border-chip pb-2.5 pt-2 font-semibold",
                    i === 0 ? "pr-2" : i === 5 ? "pl-2" : "px-2",
                    h === "Load" && "w-[150px]",
                  )}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {zones.map((z) => {
              const live = z.freshness === "live" && z.occupied !== null;
              const pct = live ? Math.round(((z.occupied ?? 0) / z.capacity) * 100) : 0;
              const chip = zoneChip(z);
              const cell = "border-b border-line-soft py-3";
              return (
                <tr key={z.zone_id} className={live ? "text-ink" : "text-[#4A524E]"}>
                  <td className={cx(cell, "pr-2")}>
                    <div className="flex flex-col">
                      <span className="font-bold">{z.name}</span>
                      <span className="text-xs text-muted">{z.canteen_name}</span>
                    </div>
                  </td>
                  <td className={cx(cell, "px-2 font-mono")}>{z.capacity}</td>
                  <td className={cx(cell, "px-2")}>
                    <span className="font-mono font-semibold">{live ? z.occupied : "—"}</span>{" "}
                    <span className="text-xs text-muted">
                      {live && z.occupied_range ? `(${z.occupied_range[0]}–${z.occupied_range[1]})` : "hidden"}
                    </span>
                  </td>
                  <td className={cx(cell, "px-2")}>
                    <div className="flex items-center gap-2">
                      <div aria-hidden="true" className="h-1.5 flex-1 overflow-hidden rounded-[3px] bg-chip">
                        <div className={cx("h-full", live ? LEVELS[z.level].bar : "bg-dash")} style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-[38px] text-right font-mono text-[13px]">{live ? `${pct}%` : "—"}</span>
                    </div>
                  </td>
                  <td className={cx(cell, "px-2")}>
                    <span className={cx(CHIP, chip.className)}>
                      <Icon name={chip.icon} size={13} strokeWidth={2.4} />
                      {chip.label}
                    </span>
                  </td>
                  <td className={cx(cell, "whitespace-nowrap pl-2 text-[13px] text-muted")}>{formatAgo(z.updated_at, now)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function AlertItem({ alert, now }: { alert: StaffAlert; now: number }) {
  const acknowledge = useAcknowledgeAlert();
  const open = alert.status === "open";
  const time = <span className="text-xs text-muted">{formatClock(alert.opened_at)}</span>;
  if (alert.type === "crowding") {
    const level = alert.level ?? "crowded";
    return (
      <li className={cx("flex flex-col gap-2 rounded-xl border px-3.5 py-3", open ? "border-alert-line bg-alert-surface" : "border-chip")}>
        <div className="flex items-center justify-between gap-2">
          <span className={cx(CHIP, "py-[3px] font-bold", LEVELS[level].pill)}>
            <Icon name={ZONE_ICON[level] ?? "warning"} size={13} strokeWidth={2.4} />
            {LEVELS[level].label}
          </span>
          {time}
        </div>
        <span className="text-sm font-bold">{alert.title}</span>
        {open ? (
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-alert-meta">Awaiting acknowledgement</span>
            <button
              type="button"
              disabled={acknowledge.isPending}
              onClick={() => acknowledge.mutate(alert.id)}
              className="min-h-9 rounded-lg border-0 bg-brand px-3 text-[13px] font-bold text-white hover:bg-brand-dark disabled:opacity-60"
            >
              {acknowledge.isPending ? "Saving…" : "Acknowledge"}
            </button>
          </div>
        ) : (
          <span className="inline-flex items-center gap-[5px] text-xs font-semibold text-ok">
            <Icon name="checkCircle" size={13} strokeWidth={2.4} />
            Acknowledged by {alert.acknowledged_by} · {alert.acknowledged_at ? formatClock(alert.acknowledged_at) : ""}
          </span>
        )}
      </li>
    );
  }
  const offline = alert.type === "sensor_offline";
  const minutes = formatMinutes(now - Date.parse(alert.opened_at));
  return (
    <li className={cx("flex flex-col gap-1.5 rounded-xl border px-3.5 py-3", offline ? "border-chip" : "border-dashed border-dash")}>
      <div className="flex items-center justify-between gap-2">
        <span className={cx(CHIP, "bg-chip py-[3px] font-bold text-neutral-ink")}>
          <Icon name={offline ? "camera" : "clock"} size={13} strokeWidth={2.4} />
          {offline ? "Sensor offline" : "Data stale"}
        </span>
        {time}
      </div>
      <span className="text-sm font-bold">{alert.title}</span>
      <span className="text-xs text-muted">
        {offline ? `No heartbeat for ${minutes}` : `No readings for ${minutes}`}
        {alert.detail ? ` · ${alert.detail}` : ""}
      </span>
    </li>
  );
}

function AlertQueue({ alerts, now }: { alerts: StaffAlert[]; now: number }) {
  const active = alerts.filter((a) => a.status !== "resolved");
  return (
    <Card labelledBy="alerts-title" className="flex-[1_1_320px] gap-3">
      <div className="flex items-center justify-between">
        <h2 id="alerts-title" className="m-0 text-[17px] font-extrabold">
          Alert queue
        </h2>
        <Link to="/alerts" className="text-[13px] font-semibold text-brand no-underline hover:text-brand-dark">
          View all
        </Link>
      </div>
      {active.length === 0 ? <span className="text-sm text-muted">No open alerts</span> : null}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {active.map((a) => (
          <AlertItem key={a.id} alert={a} now={now} />
        ))}
      </ul>
    </Card>
  );
}

function axisLabels(points: OccupancyPoint[], now: number): { index: number; text: string; strong?: boolean }[] {
  const nowIndex = points.reduce((last, p, i) => (!p.is_forecast ? i : last), -1);
  const marks = points
    .map((p, index) => ({ index, hm: formatClock24(p.at) }))
    .filter((m) => (m.hm.endsWith(":00") || m.hm.endsWith(":30")) && Math.abs(m.index - nowIndex) >= 2)
    .map((m) => ({ index: m.index, text: m.hm }));
  return nowIndex >= 0 ? [...marks, { index: nowIndex, text: `now ${formatClock24(now)}`, strong: true }] : marks;
}

function OccupancyChart({ title, points, now }: { title: string; points: OccupancyPoint[]; now: number }) {
  const labels = axisLabels(points, now);
  return (
    <Card labelledBy="chart-title" className="flex-[2_1_620px] gap-3.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <h2 id="chart-title" className="m-0 text-[17px] font-extrabold">
            {title}
          </h2>
          <span className="text-xs text-muted">10-minute averages, % of monitored seats</span>
        </div>
        <div className="flex items-center gap-3.5 text-xs text-ink-2">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-[3px] bg-brand" />
            Measured
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="forecast-stripes h-3 w-3 rounded-[3px]" />
            Forecast (experimental)
          </span>
        </div>
      </div>
      <div className="relative h-[220px] pl-10">
        <div className="absolute bottom-[80%] left-10 right-0 border-t-[1.5px] border-dashed border-crowd-mark" />
        <span className="absolute bottom-[80%] left-0 translate-y-1/2 text-[11px] font-bold text-crowd">80%</span>
        <div className="absolute bottom-[60%] left-10 right-0 border-t-[1.5px] border-dashed border-busy-mark" />
        <span className="absolute bottom-[60%] left-0 translate-y-1/2 text-[11px] font-bold text-busy">60%</span>
        <div className="absolute bottom-0 left-10 right-0 border-t border-line" />
        <ul className="relative m-0 flex h-full list-none items-end gap-1.5 p-0">
          {points.map((p) => (
            <li key={p.at} className="flex h-full flex-1 items-end">
              <span className="sr-only">
                {formatClock24(p.at)} {p.is_forecast ? "forecast" : "measured"} {p.percent}%
              </span>
              <div
                aria-hidden="true"
                title={`${p.is_forecast ? "Forecast" : "Measured"} ${p.percent}%`}
                className={cx("w-full rounded-t", p.is_forecast ? "forecast-stripes" : p.percent >= 80 ? "bg-crowd-mark" : "bg-brand")}
                style={{ height: `${p.percent}%` }}
              />
            </li>
          ))}
        </ul>
      </div>
      <div aria-hidden="true" className="relative ml-10 h-4 font-mono text-[11px] text-muted">
        {labels.map((l) => (
          <span
            key={l.index}
            className={cx("absolute -translate-x-1/2 whitespace-nowrap", l.strong && "font-semibold text-ink")}
            style={{ left: `${((l.index + 0.5) / points.length) * 100}%` }}
          >
            {l.text}
          </span>
        ))}
      </div>
      <p className="m-0 text-xs text-muted">
        Forecast = blend of current reading and historical average for this weekday. Shown as experimental until evaluated against manual
        counts.
      </p>
    </Card>
  );
}

function SafetyCard({ safety, now }: { safety: ConsoleOverview["safety"]; now: number }) {
  const active = safety.events.filter((e) => e.status !== "resolved");
  return (
    <Card labelledBy="safety-title" className="gap-2.5">
      <div className="flex items-center justify-between">
        <h2 id="safety-title" className="m-0 inline-flex items-center gap-2 text-[17px] font-extrabold">
          <Icon name="shield" size={18} />
          Safety
        </h2>
        {safety.simulation_mode ? <SimulationLabel>SIMULATION MODE</SimulationLabel> : null}
      </div>
      {active.length === 0 ? (
        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-ok">
          <Icon name="checkCircle" size={16} strokeWidth={2.4} />
          No active safety events
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-danger-ink">
          <Icon name="flame" size={16} />
          {active.length} {active.every((e) => e.is_simulation) ? "simulated " : ""}
          {active.length === 1 ? "event" : "events"} active
        </span>
      )}
      <span className="text-xs text-muted">
        Source: {safety.source.name} · {safety.source.online ? "online" : "offline"} · last heartbeat{" "}
        {formatAgo(safety.source.last_heartbeat_at, now)}
      </span>
      <span className="text-xs text-muted">
        Real alarm integration: {safety.real_integration_connected ? "connected" : "not connected (requires university approval)"}
      </span>
      <Link
        to="/safety"
        className="inline-flex min-h-11 items-center justify-center rounded-[10px] border border-line text-sm font-bold text-ink no-underline hover:bg-page"
      >
        Open safety dashboard
      </Link>
    </Card>
  );
}

const DEVICE_TONE: Record<DeviceHealth["status"], { text: string; dot: string; label: string }> = {
  ok: { text: "text-ok", dot: "bg-ok-mark", label: "OK" },
  not_reporting: { text: "text-busy", dot: "bg-busy-mark", label: "Not reporting" },
  offline: { text: "text-danger-ink", dot: "bg-full-mark", label: "Offline" },
};

function deviceMeta(d: DeviceHealth, now: number): string {
  if (d.status === "ok") return d.fps === null ? "readings arriving" : `${d.fps.toFixed(1)} fps · ${d.latency_ms ?? "—"} ms`;
  if (d.status === "not_reporting") return `last reading ${formatAgo(d.last_seen_at, now)}`;
  if (d.last_seen_at === null) return "never connected";
  return `no heartbeat ${formatMinutes(now - Date.parse(d.last_seen_at))}`;
}

function DeviceList({ devices, now }: { devices: DeviceHealth[]; now: number }) {
  return (
    <Card labelledBy="dev-title" className="gap-1">
      <h2 id="dev-title" className="m-0 mb-1.5 text-[17px] font-extrabold">
        Device health
      </h2>
      <ul className="m-0 flex list-none flex-col p-0">
        {devices.map((d, i) => {
          const tone = DEVICE_TONE[d.status];
          return (
            <li
              key={d.id}
              className={cx("flex items-center justify-between gap-2.5 py-[9px]", i < devices.length - 1 && "border-b border-line-soft")}
            >
              <div className="flex min-w-0 flex-col">
                <span className="font-mono text-[13px] font-semibold">{d.id}</span>
                <span className="text-xs text-muted">{d.where}</span>
              </div>
              <div className="flex flex-col items-end">
                <span className={cx("inline-flex items-center gap-1.5 text-[13px] font-bold", tone.text)}>
                  <span className={cx("h-2 w-2 rounded-full", tone.dot)} />
                  {tone.label}
                </span>
                <span className="text-[11px] text-muted">{deviceMeta(d, now)}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function SafetyEventBanner({ safety }: { safety: ConsoleOverview["safety"] }) {
  return (
    <>
      {safety.events
        .filter((e) => e.status !== "resolved")
        .map((e) => (
          <HazardFrame
            key={e.id}
            className="rounded-2xl p-1"
            innerClassName="flex flex-wrap items-center justify-between gap-3 rounded-[13px] px-[18px] py-3.5"
          >
            <div className="flex flex-col gap-1.5">
              {e.is_simulation ? <SimulationLabel /> : null}
              <span className="inline-flex items-center gap-2 text-[17px] font-extrabold text-danger-ink">
                <Icon name="flame" size={20} />
                {e.title}
                {e.canteen_name ? ` · ${e.canteen_name}` : ""}
              </span>
              <span className="text-[13px] text-danger-body">
                Source: {e.source_name} · received {formatClock(e.occurred_at)} · {e.status === "active" ? "unacknowledged" : e.status}
              </span>
            </div>
            <Link
              to="/safety"
              className="inline-flex min-h-11 items-center rounded-[10px] bg-danger-ink px-[18px] text-sm font-bold text-white no-underline hover:text-white"
            >
              Review in safety dashboard
            </Link>
          </HazardFrame>
        ))}
    </>
  );
}

export function OverviewScreen() {
  const overview = useConsoleOverview();
  const now = useServerNow(1000);
  const data = overview.data;
  const liveStamps = data?.zones.filter((z) => z.freshness === "live" && z.updated_at).map((z) => Date.parse(z.updated_at ?? "")) ?? [];
  const latest = liveStamps.length > 0 ? Math.max(...liveStamps) : null;
  const k = data ? kpis(data) : null;
  return (
    <main id="main" className="box-border flex min-w-0 flex-[999_1_560px] flex-col gap-5 px-8 pb-10 pt-7">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2.5">
            <h1 className="m-0 text-[28px] font-extrabold tracking-[-0.02em]">Overview</h1>
            {data?.is_sample ? <SampleBadge className="font-bold">SAMPLE DATA</SampleBadge> : null}
          </div>
          <span className="text-sm text-muted">
            {formatDateLine(now)} · {formatClock(now)} · Asia/Colombo
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <MealChip now={now} />
          <button
            type="button"
            onClick={() => void overview.refetch()}
            className="inline-flex min-h-11 items-center gap-2 rounded-[10px] border border-line bg-card px-3.5 text-sm font-semibold text-ink hover:bg-page"
          >
            <Icon name="refresh" size={16} className={overview.isFetching ? "motion-safe:animate-spin" : undefined} />
            {latest && Number.isFinite(latest) ? `Live · ${formatAgo(latest, now)}` : "Refresh"}
          </button>
        </div>
      </header>

      {overview.isError && !data ? (
        <div role="alert" className="rounded-2xl border border-dashed border-dash bg-card p-5 text-sm font-semibold">
          Couldn't load the overview. Retrying automatically…
        </div>
      ) : null}

      {k ? (
        <section aria-label="Key figures" className="flex flex-wrap gap-4">
          <Kpi
            title="Zones with live data"
            value={String(k.live)}
            suffix={`of ${data?.zones.length ?? 0}`}
            sub={`${k.stale} stale · ${k.unavailable} unavailable`}
          />
          <Kpi
            title="Free seats (live zones, est.)"
            value={`~${k.free}`}
            suffix={`${k.low}–${k.high}`}
            sub={`of ${k.capacity} monitored seats`}
          />
          <Kpi
            title="Open crowding alerts"
            value={String(k.crowding)}
            sub={`${k.awaiting} awaiting acknowledgement`}
            tone={k.crowding > 0 ? "alert" : undefined}
          />
          <Kpi
            title="Devices needing attention"
            value={String(k.attention)}
            suffix={`of ${data?.devices.length ?? 0}`}
            sub={`${k.offline} offline · ${k.notReporting} not reporting`}
          />
        </section>
      ) : (
        <div role="status" aria-label="Loading overview" className="flex flex-wrap gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} aria-hidden="true" className="h-[118px] flex-[1_1_200px] rounded-2xl bg-line-soft motion-safe:animate-pulse" />
          ))}
        </div>
      )}

      {data ? (
        <>
          <SafetyEventBanner safety={data.safety} />
          <div className="flex flex-wrap items-start gap-5">
            <ZoneTable zones={data.zones} now={now} />
            <AlertQueue alerts={data.alerts} now={now} />
          </div>
          <div className="flex flex-wrap items-start gap-5">
            <OccupancyChart
              title={`${data.occupancy_today.canteen_name} — occupancy today`}
              points={data.occupancy_today.points}
              now={now}
            />
            <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-5">
              <SafetyCard safety={data.safety} now={now} />
              <DeviceList devices={data.devices} now={now} />
            </div>
          </div>
        </>
      ) : null}
    </main>
  );
}
