import type {
  BusinessSettings,
  CameraHealth,
  CustomerDay,
  FloorTable,
  HeatCell,
  LayoutZoneSeats,
  ReportRange,
  SeatPoint,
  TableShape,
  TableStateName,
  VenueCameras,
  VenueFloor,
  VenueList,
  VenueReport,
} from "../types";
import { colomboDate, iso } from "./time";

export const SAMPLE_VENUE_ID = "v-sample-cafe";
const ZONES = [
  { id: "z-window", name: "Window side" },
  { id: "z-main", name: "Main floor" },
];
const MIN = 60_000;

interface TableSeed {
  name: string;
  zone: string;
  shape: TableShape;
  box: [number, number, number, number];
  seats: number;
  state: TableStateName;
  party: number;
  minutes: number;
  estimate?: [number, number];
  plates?: boolean;
}

const TABLES: TableSeed[] = [
  {
    name: "T1",
    zone: "z-window",
    shape: "round",
    box: [0.04, 0.06, 0.11, 0.15],
    seats: 2,
    state: "occupied",
    party: 2,
    minutes: 24,
    estimate: [10, 20],
  },
  {
    name: "T2",
    zone: "z-window",
    shape: "round",
    box: [0.19, 0.06, 0.11, 0.15],
    seats: 2,
    state: "needs_clearing",
    party: 0,
    minutes: 4,
    plates: true,
  },
  { name: "T3", zone: "z-window", shape: "rect", box: [0.34, 0.06, 0.13, 0.15], seats: 2, state: "free", party: 0, minutes: 12 },
  {
    name: "T4",
    zone: "z-window",
    shape: "rect",
    box: [0.04, 0.32, 0.19, 0.16],
    seats: 4,
    state: "occupied",
    party: 3,
    minutes: 58,
    estimate: [5, 10],
  },
  {
    name: "T5",
    zone: "z-main",
    shape: "rect",
    box: [0.27, 0.32, 0.19, 0.16],
    seats: 4,
    state: "occupied",
    party: 4,
    minutes: 41,
    estimate: [15, 25],
  },
  { name: "T6", zone: "z-window", shape: "rect", box: [0.04, 0.55, 0.19, 0.16], seats: 4, state: "held", party: 0, minutes: 9 },
  { name: "T7", zone: "z-main", shape: "rect", box: [0.27, 0.55, 0.19, 0.16], seats: 4, state: "free", party: 0, minutes: 20 },
  {
    name: "T8",
    zone: "z-main",
    shape: "rect",
    box: [0.54, 0.32, 0.19, 0.16],
    seats: 4,
    state: "occupied",
    party: 2,
    minutes: 18,
    estimate: [15, 30],
  },
  {
    name: "T9",
    zone: "z-main",
    shape: "rect",
    box: [0.54, 0.55, 0.19, 0.16],
    seats: 4,
    state: "occupied",
    party: 3,
    minutes: 33,
    estimate: [15, 20],
  },
  { name: "T10", zone: "z-main", shape: "round", box: [0.78, 0.32, 0.11, 0.15], seats: 2, state: "free", party: 0, minutes: 7 },
  {
    name: "T11",
    zone: "z-main",
    shape: "round",
    box: [0.78, 0.55, 0.11, 0.15],
    seats: 2,
    state: "occupied",
    party: 2,
    minutes: 47,
    estimate: [5, 10],
  },
  {
    name: "T12",
    zone: "z-main",
    shape: "rect",
    box: [0.54, 0.78, 0.35, 0.16],
    seats: 6,
    state: "occupied",
    party: 6,
    minutes: 52,
    estimate: [20, 35],
  },
];

const cleared = new Map<string, number>();

function tableId(name: string): string {
  return `sample-${name.toLowerCase()}`;
}

function seatPoints(t: TableSeed): SeatPoint[] {
  const [x, y, w, h] = t.box;
  const top = Math.ceil(t.seats / 2);
  const bottom = t.seats - top;
  const row = (count: number, offset: number, yy: number): SeatPoint[] =>
    Array.from({ length: count }, (_, i) => ({
      seat_id: `${t.name}-${offset + i + 1}`,
      x: Math.round((x + (w * (i + 1)) / (count + 1)) * 1e4) / 1e4,
      y: Math.round(yy * 1e4) / 1e4,
    }));
  return [...row(top, 0, y + h * 0.3), ...row(bottom, top, y + h * 0.7)];
}

function floorTable(t: TableSeed, now: number): FloorTable {
  const wasCleared = cleared.has(tableId(t.name)) && t.state === "needs_clearing";
  const state: TableStateName = wasCleared ? "free" : t.state;
  const occupied = state === "occupied";
  const [x, y, w, h] = t.box;
  return {
    id: tableId(t.name),
    name: t.name,
    zone_id: t.zone,
    zone_name: ZONES.find((z) => z.id === t.zone)?.name ?? "",
    shape: t.shape,
    x,
    y,
    w,
    h,
    seats: t.seats,
    state,
    party_size: occupied ? t.party : 0,
    since: iso(now - t.minutes * MIN),
    seated_min: occupied ? t.minutes : null,
    plates_left: !wasCleared && Boolean(t.plates),
    estimate: occupied && t.estimate ? { low_min: t.estimate[0], high_min: t.estimate[1] } : null,
  };
}

export function sampleVenues(now: number): VenueList {
  return {
    server_time: iso(now),
    items: [
      {
        id: SAMPLE_VENUE_ID,
        name: "Sample Café",
        organization_name: "Sample Café Group",
        is_sample: true,
        zones: ZONES,
        tables: TABLES.length,
      },
    ],
  };
}

export function sampleFloor(venueId: string, now: number): VenueFloor | undefined {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  const tables = TABLES.map((t) => floorTable(t, now));
  return {
    server_time: iso(now),
    venue_id: SAMPLE_VENUE_ID,
    venue_name: "Sample Café",
    is_sample: true,
    updated_at: iso(now - 4_000),
    totals: {
      tables: tables.length,
      free: tables.filter((t) => t.state === "free").length,
      guests_seated: tables.reduce((sum, t) => sum + t.party_size, 0),
      visits_today: 64,
      avg_stay_today_min: 38,
      turns_today: 5.3,
    },
    tables,
  };
}

export function sampleMarkCleared(tableIdValue: string, now: number): VenueFloor | undefined {
  if (!TABLES.some((t) => tableId(t.name) === tableIdValue)) return undefined;
  cleared.set(tableIdValue, now);
  return sampleFloor(SAMPLE_VENUE_ID, now);
}

const HOURS = [0, 0, 0, 0, 0, 0, 0, 6, 11, 18, 14, 9, 22, 31, 27, 15, 12, 16, 10, 7, 4, 0, 0, 0];
const STAYS = [29, 22, 24, 41, 44, 38, 35, 36, 33, 22, 26, 52];

export function sampleCustomers(venueId: string, now: number): CustomerDay | undefined {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  return {
    server_time: iso(now),
    venue_id: SAMPLE_VENUE_ID,
    day: colomboDate(now),
    is_sample: true,
    visits: 191,
    visits_last_week: 170,
    guests: 412,
    avg_stay_min: 38,
    median_stay_min: 31,
    turns_per_table: 4.9,
    by_hour: HOURS.map((visits, hour) => ({ hour, visits })),
    by_table: TABLES.map((t, i) => ({
      table_id: tableId(t.name),
      name: t.name,
      seats: t.seats,
      avg_stay_min: STAYS[i] ?? null,
      turns: t.seats <= 2 ? 7 : t.seats <= 4 ? 5 : 3,
    })),
  };
}

const WEEK = [168, 175, 181, 190, 191, 236, 214];

export function sampleReport(venueId: string, range: ReportRange, now: number): VenueReport | undefined {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  const count = range === "day" ? 1 : 7;
  const days = Array.from({ length: count }, (_, i) => {
    const offset = count - 1 - i;
    const visits = WEEK[(WEEK.length - 1 - offset + WEEK.length) % WEEK.length] ?? 180;
    return {
      day: colomboDate(now - offset * 86_400_000),
      visits,
      guests: Math.round(visits * 2.15),
      avg_stay_min: 34 + ((offset * 3) % 8),
    };
  });
  const heat: HeatCell[] = [];
  for (let weekday = 0; weekday < 7; weekday++) {
    for (let hour = 7; hour < 21; hour++) {
      const base = HOURS[hour] ?? 0;
      const weekend = weekday >= 5 ? 1.3 : 1;
      heat.push({ weekday, hour, visits: Math.round(base * 4 * weekend) });
    }
  }
  return { server_time: iso(now), venue_id: SAMPLE_VENUE_ID, range, is_sample: true, days, heat, heat_days: 28 };
}

export function sampleCameras(venueId: string, now: number): VenueCameras | undefined {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  const items: CameraHealth[] = [
    { id: "sim-cafe", kind: "simulator", zones: ["Window side", "Main floor"], status: "ok", fps: null, last_seen_at: iso(now - 4_000) },
    { id: "cam-entrance", kind: "camera", zones: [], status: "offline", fps: null, last_seen_at: iso(now - 2 * MIN) },
  ];
  return { server_time: iso(now), venue_id: SAMPLE_VENUE_ID, items };
}

export function sampleTableLayout(venueId: string, now: number) {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  const zones: LayoutZoneSeats[] = ZONES.map((z) => ({
    zone_id: z.id,
    name: z.name,
    seats: TABLES.filter((t) => t.zone === z.id).flatMap(seatPoints),
  }));
  return {
    server_time: iso(now),
    venue_id: SAMPLE_VENUE_ID,
    zones,
    tables: TABLES.map((t) => {
      const [x, y, w, h] = t.box;
      return {
        id: tableId(t.name),
        name: t.name,
        zone_id: t.zone,
        shape: t.shape,
        x,
        y,
        w,
        h,
        seat_ids: seatPoints(t).map((p) => p.seat_id),
      };
    }),
  };
}

export function sampleBusinessSettings(now: number): BusinessSettings {
  return { server_time: iso(now), organization_id: "sample-cafe-group", organization_name: "Sample Café Group", retention_days: 90 };
}
