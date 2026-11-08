import type { CanteenSeats, SeatOverview, ZoneSeats } from "../types";
import { canteenDetail, canteenIds } from "./student";
import { iso } from "./time";

const HELD_SHARE = 0.12;
const FREE_SOON_SHARE = 0.08;

function zoneSeats(id: string, now: number): ZoneSeats[] {
  const detail = canteenDetail(id, now);
  if (!detail) return [];
  return detail.zones
    .filter((z) => z.free_about !== null)
    .map((z) => {
      const taken = z.capacity - (z.free_about ?? 0);
      const held = Math.round(taken * HELD_SHARE);
      const crowded = z.level === "crowded" || z.level === "near_capacity";
      const unknown = crowded ? Math.min(2, z.free_about ?? 0) : 0;
      const free = (z.free_about ?? 0) - unknown;
      return {
        zone_id: z.zone_id,
        name: z.name,
        freshness: z.freshness,
        seats: z.capacity,
        free,
        occupied: taken - held,
        held,
        unknown,
        free_soon: Math.round((taken - held) * FREE_SOON_SHARE),
        standing: crowded ? 5 : 1,
        crowded,
        updated_at: z.updated_at,
      };
    });
}

function totals(zones: ZoneSeats[]): Pick<CanteenSeats, "held" | "free_soon" | "crowded_zones"> {
  return {
    held: zones.reduce((sum, z) => sum + (z.held ?? 0), 0),
    free_soon: zones.reduce((sum, z) => sum + (z.free_soon ?? 0), 0),
    crowded_zones: zones.filter((z) => z.crowded).length,
  };
}

export function sampleCanteenSeats(id: string, now: number): CanteenSeats | undefined {
  if (!canteenIds().some((c) => c.id === id)) return undefined;
  const zones = zoneSeats(id, now);
  return { server_time: iso(now), canteen_id: id, zones, ...totals(zones) };
}

export function sampleSeatOverview(now: number): SeatOverview {
  return {
    server_time: iso(now),
    items: canteenIds().map(({ id }) => {
      const zones = zoneSeats(id, now);
      return { canteen_id: id, zones_with_seats: zones.length, ...totals(zones) };
    }),
  };
}
