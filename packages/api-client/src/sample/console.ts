import type { ConsoleOverview, ConsoleZone, DeviceHealth, OccupancyPoint, StaffAlert } from "../types";
import { fixedReading, iso, periodicReading, todayAt } from "./time";

const ACKNOWLEDGED_BY = "Campus administrator";

const alertState: StaffAlert[] = [];
let alertsSeeded = false;

function seedAlerts(now: number): void {
  if (alertsSeeded) return;
  alertsSeeded = true;
  alertState.push(
    {
      id: "al-a-south",
      type: "crowding",
      level: "crowded",
      title: "Canteen A — South tables",
      detail: null,
      status: "open",
      opened_at: iso(todayAt(now, "12:33")),
      acknowledged_at: null,
      acknowledged_by: null,
    },
    {
      id: "al-a-north",
      type: "crowding",
      level: "crowded",
      title: "Canteen A — North tables",
      detail: null,
      status: "acknowledged",
      opened_at: iso(todayAt(now, "12:21")),
      acknowledged_at: iso(todayAt(now, "12:24")),
      acknowledged_by: "canteen manager",
    },
    {
      id: "al-c-main",
      type: "sensor_offline",
      level: null,
      title: "cam-c3-z1 · Canteen C — Main hall",
      detail: "seat numbers hidden from students",
      status: "open",
      opened_at: iso(todayAt(now, "12:27")),
      acknowledged_at: null,
      acknowledged_by: null,
    },
    {
      id: "al-c-upper",
      type: "data_stale",
      level: null,
      title: "Canteen C — Upper deck",
      detail: "stream online",
      status: "open",
      opened_at: iso(todayAt(now, "12:35")),
      acknowledged_at: null,
      acknowledged_by: null,
    },
  );
}

function zones(now: number): ConsoleZone[] {
  const live = (ageS: number) => iso(periodicReading(now, ageS, 60));
  return [
    {
      zone_id: "z-a-north",
      name: "North tables",
      canteen_name: "Canteen A",
      capacity: 36,
      freshness: "live",
      level: "crowded",
      occupied: 29,
      occupied_range: [26, 32],
      updated_at: live(40),
    },
    {
      zone_id: "z-a-south",
      name: "South tables",
      canteen_name: "Canteen A",
      capacity: 40,
      freshness: "live",
      level: "crowded",
      occupied: 32,
      occupied_range: [29, 35],
      updated_at: live(40),
    },
    {
      zone_id: "z-b-garden",
      name: "Garden side",
      canteen_name: "Canteen B",
      capacity: 32,
      freshness: "live",
      level: "busy",
      occupied: 20,
      occupied_range: [17, 23],
      updated_at: live(25),
    },
    {
      zone_id: "z-b-indoor",
      name: "Indoor",
      canteen_name: "Canteen B",
      capacity: 28,
      freshness: "live",
      level: "busy",
      occupied: 18,
      occupied_range: [15, 21],
      updated_at: live(25),
    },
    {
      zone_id: "z-c-upper",
      name: "Upper deck",
      canteen_name: "Canteen C",
      capacity: 24,
      freshness: "stale",
      level: "unknown",
      occupied: null,
      occupied_range: null,
      updated_at: iso(fixedReading(378)),
    },
    {
      zone_id: "z-c-main",
      name: "Main hall",
      canteen_name: "Canteen C",
      capacity: 48,
      freshness: "unavailable",
      level: "unknown",
      occupied: null,
      occupied_range: null,
      updated_at: iso(fixedReading(858)),
    },
  ];
}

function devices(now: number): DeviceHealth[] {
  const beat = (ageS: number) => iso(periodicReading(now, ageS, 15));
  return [
    { id: "cam-c1-z1", where: "Canteen A · North tables", status: "ok", fps: 4.2, latency_ms: 310, last_seen_at: beat(4) },
    { id: "cam-c1-z2", where: "Canteen A · South tables", status: "ok", fps: 4.0, latency_ms: 340, last_seen_at: beat(7) },
    { id: "cam-c2-z1", where: "Canteen B · both zones", status: "ok", fps: 4.5, latency_ms: 290, last_seen_at: beat(2) },
    {
      id: "cam-c3-z2",
      where: "Canteen C · Upper deck",
      status: "not_reporting",
      fps: null,
      latency_ms: null,
      last_seen_at: iso(fixedReading(378)),
    },
    {
      id: "cam-c3-z1",
      where: "Canteen C · Main hall",
      status: "offline",
      fps: null,
      latency_ms: null,
      last_seen_at: iso(fixedReading(858)),
    },
  ];
}

function occupancyToday(now: number): OccupancyPoint[] {
  const measured = [18, 22, 30, 41, 52, 61, 70, 76, 79, 81, 80];
  const forecast = [78, 72, 63, 52, 41, 32, 25, 18];
  const start = todayAt(now, "11:00");
  const step = 10 * 60_000;
  return [
    ...measured.map((percent, i) => ({ at: iso(start + i * step), percent, is_forecast: false })),
    ...forecast.map((percent, i) => ({ at: iso(start + (measured.length + i) * step), percent, is_forecast: true })),
  ];
}

export function consoleOverview(now: number): ConsoleOverview {
  seedAlerts(now);
  return {
    server_time: iso(now),
    is_sample: true,
    zones: zones(now),
    alerts: alertState.map((a) => ({ ...a })),
    devices: devices(now),
    occupancy_today: { canteen_name: "Canteen A", points: occupancyToday(now) },
    safety: {
      simulation_mode: true,
      events: [],
      source: { name: "Safety simulator", online: true, last_heartbeat_at: iso(periodicReading(now, 8, 10)) },
      real_integration_connected: false,
    },
  };
}

export function acknowledgeAlert(id: string, now: number): StaffAlert | undefined {
  seedAlerts(now);
  const alert = alertState.find((a) => a.id === id);
  if (!alert || alert.status !== "open") return alert;
  alert.status = "acknowledged";
  alert.acknowledged_at = iso(now);
  alert.acknowledged_by = ACKNOWLEDGED_BY;
  return { ...alert };
}
