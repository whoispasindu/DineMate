import { serverNow, syncServerTime } from "./clock";
import { acknowledgeAlert, consoleOverview } from "./sample/console";
import { mealStatus } from "./sample/schedule";
import { menuItems, shopById, shopsFor } from "./sample/shops";
import { alertFeed, canteenDetail, canteenIds, studentSummary } from "./sample/student";
import { iso, sampleNow } from "./sample/time";
import type {
  AlertFeed,
  CanteenDetail,
  CanteenSummary,
  ConsoleOverview,
  ErrorResponse,
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
    readonly requestId: string | null = null,
  ) {
    super(message);
  }
}

let baseUrl: string | null = null;
let staffToken: string | null = null;

export function configureApi(options: { baseUrl?: string | null; staffToken?: string | null }): void {
  const url = options.baseUrl?.trim();
  baseUrl = url ? url.replace(/\/+$/, "") : null;
  staffToken = options.staffToken?.trim() || null;
}

export function apiMode(): "api" | "sample" {
  return baseUrl === null ? "sample" : "api";
}

interface RequestOptions {
  method?: "GET" | "POST";
  staff?: boolean;
}

async function fromApi<T extends Timestamped>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.staff && staffToken) headers.Authorization = `Bearer ${staffToken}`;
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { method: options.method ?? "GET", headers });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the DineMate server.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as ErrorResponse | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "error",
      error?.message ?? response.statusText,
      (body as ErrorResponse | null)?.request_id ?? null,
    );
  }
  const result = body as T;
  syncServerTime(result.server_time);
  return result;
}

async function fromSample<T extends Timestamped>(build: (now: number) => T | undefined, notFound: string): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, SAMPLE_LATENCY_MS));
  const usingApiClock = baseUrl !== null;
  const result = build(usingApiClock ? serverNow() : sampleNow());
  if (!result) throw new ApiError(404, "not_found", notFound);
  if (!usingApiClock) syncServerTime(result.server_time);
  return structuredClone(result);
}

function either<T extends Timestamped>(path: string, build: (now: number) => T | undefined, notFound: string): Promise<T> {
  return baseUrl === null ? fromSample(build, notFound) : fromApi<T>(path);
}

const enc = encodeURIComponent;

export const api = {
  studentSummary: (): Promise<StudentSummary> => either("/student/summary", studentSummary, "Summary unavailable"),
  canteen: (id: string): Promise<CanteenDetail> => either(`/canteens/${enc(id)}`, (now) => canteenDetail(id, now), "Canteen not found"),
  canteens: (): Promise<{ server_time: string; items: Pick<CanteenSummary, "id" | "name">[] }> =>
    either("/canteens", (now) => ({ server_time: iso(now), items: canteenIds() }), "Canteens unavailable"),
  shops: (canteenId: string): Promise<ShopList> =>
    either(
      `/canteens/${enc(canteenId)}/shops`,
      (now) => ({ server_time: iso(now), canteen_id: canteenId, items: shopsFor(canteenId, now) }),
      "Canteen not found",
    ),
  menu: (shopId: string): Promise<Menu> =>
    either(
      `/shops/${enc(shopId)}/menu`,
      (now) => {
        const shop = shopById(shopId, now);
        if (!shop) return undefined;
        return { server_time: iso(now), shop_id: shopId, is_sample: true, items: menuItems(shopId), menu_updated_at: shop.menu_updated_at };
      },
      "Shop not found",
    ),
  mealStatus: (): Promise<MealStatus> => either("/meal-status", mealStatus, "Meal status unavailable"),
  alerts: (): Promise<AlertFeed> => either("/notices", alertFeed, "Alerts unavailable"),
  consoleOverview: (): Promise<ConsoleOverview> =>
    baseUrl === null ? fromSample(consoleOverview, "Overview unavailable") : fromApi<ConsoleOverview>("/console/overview", { staff: true }),
  acknowledgeAlert: (id: string): Promise<StaffAlert & Timestamped> =>
    baseUrl !== null
      ? fromApi<StaffAlert & Timestamped>(`/alerts/${enc(id)}/acknowledge`, { method: "POST", staff: true })
      : fromSample((now) => {
          const alert = acknowledgeAlert(id, now);
          return alert ? { ...alert, server_time: iso(now) } : undefined;
        }, "Alert not found"),
};
