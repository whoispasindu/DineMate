import { syncServerTime } from "./clock";
import { acknowledgeAlert, consoleOverview } from "./sample/console";
import { mealStatus } from "./sample/schedule";
import { menuItems, shopById, shopsFor } from "./sample/shops";
import { alertFeed, canteenDetail, canteenIds, studentSummary } from "./sample/student";
import { iso, sampleNow } from "./sample/time";
import type {
  AlertFeed,
  CanteenDetail,
  ConsoleOverview,
  MealStatus,
  Menu,
  ShopList,
  StaffAlert,
  StudentSummary,
  Timestamped,
} from "./types";

const SAMPLE_LATENCY_MS = 120;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function respond<T extends Timestamped>(build: (now: number) => T | undefined, notFound: string): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, SAMPLE_LATENCY_MS));
  const result = build(sampleNow());
  if (!result) throw new ApiError(404, "not_found", notFound);
  syncServerTime(result.server_time);
  return structuredClone(result);
}

export const api = {
  studentSummary: (): Promise<StudentSummary> => respond(studentSummary, "Summary unavailable"),
  canteen: (id: string): Promise<CanteenDetail> => respond((now) => canteenDetail(id, now), "Canteen not found"),
  canteens: (): Promise<{ server_time: string; items: { id: string; name: string }[] }> =>
    respond((now) => ({ server_time: iso(now), items: canteenIds() }), "Canteens unavailable"),
  shops: (canteenId: string): Promise<ShopList> =>
    respond((now) => ({ server_time: iso(now), canteen_id: canteenId, items: shopsFor(canteenId, now) }), "Canteen not found"),
  menu: (shopId: string): Promise<Menu> =>
    respond((now) => {
      const shop = shopById(shopId, now);
      if (!shop) return undefined;
      return {
        server_time: iso(now),
        shop_id: shopId,
        is_sample: true,
        items: menuItems(shopId),
        menu_updated_at: shop.menu_updated_at,
      };
    }, "Shop not found"),
  mealStatus: (): Promise<MealStatus> => respond(mealStatus, "Meal status unavailable"),
  alerts: (): Promise<AlertFeed> => respond(alertFeed, "Alerts unavailable"),
  consoleOverview: (): Promise<ConsoleOverview> => respond(consoleOverview, "Overview unavailable"),
  acknowledgeAlert: (id: string): Promise<StaffAlert & Timestamped> =>
    respond((now) => {
      const alert = acknowledgeAlert(id, now);
      return alert ? { ...alert, server_time: iso(now) } : undefined;
    }, "Alert not found"),
};
