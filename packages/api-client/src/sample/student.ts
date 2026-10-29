import type {
  AlertFeed,
  BusyPoint,
  CanteenDetail,
  CanteenSummary,
  CrowdLevel,
  ForecastPoint,
  Freshness,
  Notice,
  OpeningHours,
  RecommendationResult,
  SafetyStatus,
  StudentSummary,
  WalkTime,
  ZoneOccupancy,
} from "../types";
import { featuredShops, isOpenNow, shopsFor } from "./shops";
import { fixedReading, iso, periodicReading, todayAt } from "./time";

interface ZoneSeed {
  id: string;
  name: string;
  capacity: number;
  occupied: number | null;
  occupiedRange: [number, number] | null;
  offlineForS?: number;
}

interface CanteenSeed {
  id: string;
  name: string;
  readingAgeS: number;
  walk: WalkTime;
  hours: OpeningHours[];
  zones: ZoneSeed[];
  forecast: [string, number, number][];
}

const POST_EVERY_S = 60;
const STALE_AFTER_S = 120;
const UNAVAILABLE_AFTER_S = 600;
const THRESHOLDS = { busy: 60, crowded: 80, near_capacity: 95 };

const CANTEENS: CanteenSeed[] = [
  {
    id: "a",
    name: "Canteen A",
    readingAgeS: 40,
    walk: { from_name: "Canteen B", minutes: 4 },
    hours: [{ opens: "07:00", closes: "18:00" }],
    zones: [
      { id: "a-indoor", name: "Indoor hall", capacity: 36, occupied: 30, occupiedRange: [27, 33] },
      { id: "a-terrace", name: "Terrace", capacity: 40, occupied: 30, occupiedRange: [26, 33] },
      { id: "a-balcony", name: "Balcony", capacity: 24, occupied: null, occupiedRange: null, offlineForS: 858 },
    ],
    forecast: [
      ["13:00", 70, 80],
      ["13:15", 55, 70],
      ["13:30", 35, 50],
      ["13:45", 20, 35],
    ],
  },
  {
    id: "b",
    name: "Canteen B",
    readingAgeS: 25,
    walk: { from_name: "Canteen A", minutes: 4 },
    hours: [{ opens: "07:00", closes: "18:00" }],
    zones: [
      { id: "b-garden", name: "Garden side", capacity: 32, occupied: 14, occupiedRange: [11, 17] },
      { id: "b-indoor", name: "Indoor hall", capacity: 28, occupied: 14, occupiedRange: [11, 17] },
    ],
    forecast: [
      ["13:00", 55, 70],
      ["13:15", 50, 62],
      ["13:30", 38, 50],
      ["13:45", 25, 38],
    ],
  },
  {
    id: "c",
    name: "Canteen C",
    readingAgeS: 30,
    walk: { from_name: "Canteen A", minutes: 3 },
    hours: [{ opens: "07:30", closes: "17:00" }],
    zones: [
      { id: "c-main", name: "Main hall", capacity: 48, occupied: 43, occupiedRange: [40, 45] },
      { id: "c-upper", name: "Upper deck", capacity: 24, occupied: 20, occupiedRange: [19, 22] },
    ],
    forecast: [
      ["13:00", 80, 90],
      ["13:15", 70, 82],
      ["13:30", 50, 65],
      ["13:45", 30, 45],
    ],
  },
];

const BUSY_TODAY: BusyPoint[] = [
  { label: "10:30", percent: 12, is_forecast: false, is_now: false },
  { label: "11:00", percent: 20, is_forecast: false, is_now: false },
  { label: "11:30", percent: 41, is_forecast: false, is_now: false },
  { label: "12:00", percent: 70, is_forecast: false, is_now: false },
  { label: "Now", percent: 79, is_forecast: false, is_now: true },
  { label: "13:00", percent: 72, is_forecast: true, is_now: false },
  { label: "13:30", percent: 41, is_forecast: true, is_now: false },
  { label: "14:00", percent: 18, is_forecast: true, is_now: false },
];

function levelFor(percent: number): CrowdLevel {
  if (percent >= THRESHOLDS.near_capacity) return "near_capacity";
  if (percent >= THRESHOLDS.crowded) return "crowded";
  if (percent >= THRESHOLDS.busy) return "busy";
  return "normal";
}

function freshnessFor(updatedAt: number, now: number): Freshness {
  const ageS = (now - updatedAt) / 1000;
  if (ageS <= STALE_AFTER_S) return "live";
  if (ageS <= UNAVAILABLE_AFTER_S) return "stale";
  return "unavailable";
}

function zoneOccupancy(seed: ZoneSeed, canteen: CanteenSeed, now: number): ZoneOccupancy {
  const updatedAt =
    seed.offlineForS !== undefined ? fixedReading(seed.offlineForS) : periodicReading(now, canteen.readingAgeS, POST_EVERY_S);
  const freshness = seed.occupied === null ? "unavailable" : freshnessFor(updatedAt, now);
  const hasNumbers = freshness !== "unavailable" && seed.occupied !== null && seed.occupiedRange !== null;
  const percent = hasNumbers ? Math.round(((seed.occupied ?? 0) / seed.capacity) * 100) : null;
  return {
    zone_id: seed.id,
    name: seed.name,
    capacity: seed.capacity,
    freshness,
    level: percent === null || freshness !== "live" ? "unknown" : levelFor(percent),
    percent,
    free_about: hasNumbers ? seed.capacity - (seed.occupied ?? 0) : null,
    free_range: hasNumbers && seed.occupiedRange ? [seed.capacity - seed.occupiedRange[1], seed.capacity - seed.occupiedRange[0]] : null,
    updated_at: iso(updatedAt),
  };
}

function summarize(seed: CanteenSeed, now: number): { summary: CanteenSummary; zones: ZoneOccupancy[] } {
  const zones = seed.zones.map((z) => zoneOccupancy(z, seed, now));
  const counted = zones.filter((z) => z.freshness !== "unavailable" && z.free_range !== null);
  const live = zones.filter((z) => z.freshness === "live");
  const capacity = counted.reduce((sum, z) => sum + z.capacity, 0);
  const free = counted.reduce((sum, z) => sum + (z.free_about ?? 0), 0);
  const low = counted.reduce((sum, z) => sum + (z.free_range?.[0] ?? 0), 0);
  const high = counted.reduce((sum, z) => sum + (z.free_range?.[1] ?? 0), 0);
  const percent = capacity > 0 ? Math.round(((capacity - free) / capacity) * 100) : null;
  const freshness: Freshness = live.length > 0 ? "live" : counted.length > 0 ? "stale" : "unavailable";
  const latest = Math.max(...zones.map((z) => (z.updated_at ? Date.parse(z.updated_at) : 0)));
  const shops = shopsFor(seed.id, now);
  return {
    zones,
    summary: {
      id: seed.id,
      name: seed.name,
      is_sample: true,
      level: percent === null || freshness !== "live" ? "unknown" : levelFor(percent),
      freshness,
      percent,
      free_about: counted.length > 0 ? free : null,
      free_range: counted.length > 0 ? [low, high] : null,
      monitored_capacity: capacity,
      zones_live: live.length,
      zones_total: zones.length,
      shops_total: shops.length,
      shops_open: shops.filter(isOpenNow).length,
      walk: seed.walk,
      updated_at: iso(latest),
    },
  };
}

function pickBest(canteens: CanteenSummary[]): StudentSummary["best"] {
  const candidates = canteens
    .filter((c) => c.freshness === "live" && (c.level === "normal" || c.level === "busy") && c.free_range !== null)
    .sort((a, b) => (b.free_range?.[0] ?? 0) - (a.free_range?.[0] ?? 0));
  const best = candidates[0];
  return best ? { canteen_id: best.id, name: best.name } : null;
}

export function safetyStatus(now: number): SafetyStatus {
  return {
    active: true,
    events: [
      {
        id: "sim-000123",
        event_type: "fire_alarm",
        title: "Fire alarm (simulated)",
        canteen_name: "Canteen A",
        occurred_at: iso(todayAt(now, "12:41") + 6_000),
        is_simulation: true,
        status: "active",
        source_name: "Safety simulator",
        instructions: "Follow instructions from campus staff and official alarms.",
      },
    ],
  };
}

export function studentSummary(now: number): StudentSummary {
  const canteens = CANTEENS.map((c) => summarize(c, now).summary);
  return {
    server_time: iso(now),
    best: pickBest(canteens),
    canteens,
    shops_now: featuredShops(now),
    busy_today: { canteen_id: "a", canteen_name: "Canteen A", points: BUSY_TODAY },
    safety: safetyStatus(now),
  };
}

export function canteenDetail(id: string, now: number): CanteenDetail | undefined {
  const seed = CANTEENS.find((c) => c.id === id);
  if (!seed) return undefined;
  const { summary, zones } = summarize(seed, now);
  const forecast: ForecastPoint[] = seed.forecast.map(([at, low, high]) => ({ at: iso(todayAt(now, at)), low, high }));
  return {
    server_time: iso(now),
    canteen: summary,
    hours_today: seed.hours,
    zones,
    forecast,
    shops: shopsFor(seed.id, now),
  };
}

export function canteenIds(): { id: string; name: string }[] {
  return CANTEENS.map((c) => ({ id: c.id, name: c.name }));
}

export function alertFeed(now: number): AlertFeed {
  const notice = (n: Omit<Notice, "at"> & { at: string }): Notice => ({ ...n, at: iso(todayAt(now, n.at)) });
  return {
    server_time: iso(now),
    safety: safetyStatus(now),
    notices: [
      notice({
        id: "n-crowd-c",
        kind: "crowding",
        title: "Canteen C is crowded",
        body: "About 88% of seats in use (estimate). Canteen B has around 32 free seats, 4 min walk.",
        context: "try Canteen B",
        at: "12:35",
        related_canteen: { id: "b", name: "Canteen B" },
      }),
      notice({
        id: "n-noodle-close",
        kind: "shop_closing",
        title: "Noodle Bar closes at 1:00 p.m.",
        body: "Canteen B · earlier than usual today",
        context: "Canteen B",
        at: "12:30",
        related_canteen: null,
      }),
      notice({
        id: "n-balcony",
        kind: "data_unavailable",
        title: "Canteen A balcony — no live data",
        body: "Seat numbers for this zone are hidden until the sensor reconnects.",
        context: "Canteen A",
        at: "12:27",
        related_canteen: null,
      }),
      notice({
        id: "n-soldout-fish",
        kind: "sold_out",
        title: "Fish rice & curry sold out",
        body: "Rice & Curry Stall · Canteen A",
        context: "Rice & Curry Stall",
        at: "12:10",
        related_canteen: null,
      }),
      notice({
        id: "n-lunch",
        kind: "meal_starting",
        title: "Lunch has started",
        body: "Served until 2:00 p.m. today.",
        context: "Served until 2:00 p.m.",
        at: "11:30",
        related_canteen: null,
      }),
    ],
  };
}

export function sampleRecommendation(fromCanteen: string | null, now: number): RecommendationResult {
  const others = studentSummary(now).canteens.filter((c) => c.id !== fromCanteen);
  const eligible = others
    .filter((c) => c.freshness === "live" && (c.level === "normal" || c.level === "busy") && c.free_range !== null)
    .sort((a, b) => (b.free_range?.[0] ?? 0) - (a.free_range?.[0] ?? 0));
  const best = eligible[0];
  return {
    server_time: iso(now),
    from_canteen_id: fromCanteen,
    recommendation: best
      ? {
          canteen_id: best.id,
          name: best.name,
          level: best.level,
          free_about: best.free_about,
          available_range: best.free_range ?? [0, 0],
          walk_minutes: best.walk?.minutes ?? null,
          reason: fromCanteen ? "Lower crowding with live data" : "Most seats free with live data",
        }
      : null,
    message: best ? null : "No reliable alternative right now.",
    excluded: others
      .filter((c) => !eligible.includes(c))
      .map((c) => ({ canteen_id: c.id, name: c.name, reason: c.freshness === "live" ? "too_crowded" : "no_live_data" })),
  };
}
