import { serverNow, syncServerTime } from "./clock";
import { heldToken, setSession } from "./session";
import { acknowledgeAlert, consoleOverview } from "./sample/console";
import { mealStatus } from "./sample/schedule";
import { menuItems, shopById, shopsFor } from "./sample/shops";
import { alertFeed, canteenDetail, canteenIds, safetyStatus, sampleRecommendation, studentSummary } from "./sample/student";
import { iso, sampleNow } from "./sample/time";
import { sampleUser } from "./sample/users";
import type {
  AlertFeed,
  HistoryBucket,
  RecommendationResult,
  ZoneHistory,
  SafetyActive,
  SafetySourceList,
  StaffSafetyEventList,
  StaffSafetyEventResult,
  AvailabilityResult,
  DeviceLayout,
  EditableZone,
  LayoutPolygon,
  ManagedDeviceList,
  MealOverride,
  MealScheduleSet,
  MealSlot,
  ThresholdList,
  ThresholdResult,
  ThresholdValues,
  ZoneResult,
  HoursException,
  ManagedShopList,
  MenuItemFields,
  ShopEditor,
  WeeklyHours,
  CanteenDetail,
  CanteenSummary,
  ConsoleOverview,
  ErrorResponse,
  MealStatus,
  Menu,
  ShopList,
  StaffAlert,
  StaffSession,
  StaffUser,
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

const TOKEN_MARGIN_MS = 30_000;

export function configureApi(options: { baseUrl?: string | null }): void {
  const url = options.baseUrl?.trim();
  baseUrl = url ? url.replace(/\/+$/, "") : null;
}

export function apiMode(): "api" | "sample" {
  return baseUrl === null ? "sample" : "api";
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  staff?: boolean;
  body?: unknown;
}

async function send(path: string, options: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  try {
    return await fetch(`${baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: path.startsWith("/auth/") ? "include" : "same-origin",
    });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the DineMate server.");
  }
}

async function parse<T>(response: Response): Promise<T> {
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
  return body as T;
}

function adopt(session: StaffSession): StaffUser {
  setSession(
    { status: "signed_in", user: session.user, sample: false },
    { token: session.access_token, expiresAt: Date.now() + session.expires_in * 1000 },
  );
  return session.user;
}

let refreshing: Promise<StaffUser | null> | null = null;

function refreshSession(): Promise<StaffUser | null> {
  refreshing ??= send("/auth/refresh", { method: "POST" }, null)
    .then(async (response) => {
      if (response.status === 401) {
        setSession({ status: "signed_out" });
        return null;
      }
      return adopt(await parse<StaffSession>(response));
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function staffToken(): Promise<string | null> {
  const { token, expiresAt } = heldToken();
  if (token && expiresAt - Date.now() > TOKEN_MARGIN_MS) return token;
  await refreshSession();
  return heldToken().token;
}

async function fromApi<T extends Timestamped>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options, options.staff ? await staffToken() : null);
  if (options.staff && response.status === 401 && (await refreshSession())) {
    response = await send(path, options, heldToken().token);
  }
  const result = await parse<T>(response);
  syncServerTime(result.server_time);
  return result;
}

export async function signIn(email: string, password: string): Promise<StaffUser> {
  if (baseUrl === null) {
    await new Promise((resolve) => setTimeout(resolve, SAMPLE_LATENCY_MS));
    const user = sampleUser(email);
    if (!user || !password) throw new ApiError(401, "invalid_credentials", "Email or password is incorrect.");
    setSession({ status: "signed_in", user, sample: true });
    return user;
  }
  return adopt(await parse<StaffSession>(await send("/auth/login", { method: "POST", body: { email, password } }, null)));
}

export async function restoreSession(): Promise<StaffUser | null> {
  if (baseUrl === null) {
    setSession({ status: "signed_out" });
    return null;
  }
  try {
    return await refreshSession();
  } catch {
    setSession({ status: "signed_out" });
    return null;
  }
}

export async function signOut(): Promise<void> {
  setSession({ status: "signed_out" });
  if (baseUrl !== null) await send("/auth/logout", { method: "POST" }, null).catch(() => undefined);
}

async function fromSample<T extends Timestamped>(build: (now: number) => T | undefined, notFound: string): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, SAMPLE_LATENCY_MS));
  const usingApiClock = baseUrl !== null;
  const result = build(usingApiClock ? serverNow() : sampleNow());
  if (!result) throw new ApiError(404, "not_found", notFound);
  if (!usingApiClock) syncServerTime(result.server_time);
  return structuredClone(result);
}

function staffOnly<T extends Timestamped>(path: string, options: RequestOptions = {}): Promise<T> {
  if (baseUrl === null) {
    return Promise.reject(new ApiError(0, "needs_api", "Editing needs the real API. Start it with pnpm dev:console:api."));
  }
  return fromApi<T>(path, { ...options, staff: true });
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
  managedShops: (): Promise<ManagedShopList> => staffOnly("/manage/shops"),
  shopEditor: (shopId: string): Promise<ShopEditor> => staffOnly(`/manage/shops/${enc(shopId)}`),
  saveShopHours: (shopId: string, body: { weekly: WeeklyHours[]; exceptions: HoursException[] }): Promise<ShopEditor> =>
    staffOnly(`/shops/${enc(shopId)}/hours`, { method: "PUT", body }),
  setShopClosure: (shopId: string, body: { until: string | null; reason: string | null }): Promise<ShopEditor> =>
    staffOnly(`/shops/${enc(shopId)}/closure`, { method: "PUT", body }),
  createMenuItem: (shopId: string, body: MenuItemFields): Promise<ShopEditor> =>
    staffOnly(`/shops/${enc(shopId)}/menu-items`, { method: "POST", body }),
  editMenuItem: (itemId: string, body: Partial<MenuItemFields>): Promise<ShopEditor> =>
    staffOnly(`/menu-items/${enc(itemId)}`, { method: "PATCH", body }),
  deleteMenuItem: (itemId: string): Promise<ShopEditor> => staffOnly(`/menu-items/${enc(itemId)}`, { method: "DELETE" }),
  setAvailability: (itemId: string, isAvailable: boolean): Promise<AvailabilityResult> =>
    staffOnly(`/menu-items/${enc(itemId)}/availability`, { method: "PATCH", body: { is_available: isAvailable } }),
  publishMenu: (shopId: string): Promise<ShopEditor> => staffOnly(`/shops/${enc(shopId)}/menu/publish`, { method: "POST" }),
  discardMenu: (shopId: string): Promise<ShopEditor> => staffOnly(`/shops/${enc(shopId)}/menu/discard`, { method: "POST" }),
  mealSchedules: (canteenId: string | null): Promise<MealScheduleSet> =>
    staffOnly(canteenId ? `/manage/meal-schedules?canteen_id=${enc(canteenId)}` : "/manage/meal-schedules"),
  saveMealSchedules: (body: {
    canteen_id: string | null;
    weekly: MealSlot[] | null;
    overrides: MealOverride[];
  }): Promise<MealScheduleSet> => staffOnly("/meal-schedules", { method: "PUT", body }),
  thresholds: (): Promise<ThresholdList> => staffOnly("/manage/thresholds"),
  saveThresholds: (zoneId: string, body: ThresholdValues): Promise<ThresholdResult> =>
    staffOnly(`/zones/${enc(zoneId)}/thresholds`, { method: "PUT", body }),
  managedDevices: (): Promise<ManagedDeviceList> => staffOnly("/manage/devices"),
  deviceLayout: (deviceId: string): Promise<DeviceLayout> => staffOnly(`/devices/${enc(deviceId)}/layout`),
  saveLayout: (deviceId: string, body: { base_version: number | null; polygons: LayoutPolygon[] }): Promise<DeviceLayout> =>
    staffOnly(`/devices/${enc(deviceId)}/layout`, { method: "PUT", body }),
  rollbackLayout: (deviceId: string, version: number): Promise<DeviceLayout> =>
    staffOnly(`/devices/${enc(deviceId)}/layout/rollback`, { method: "POST", body: { version } }),
  updateZone: (zoneId: string, body: Partial<Pick<EditableZone, "name" | "capacity" | "is_active">>): Promise<ZoneResult> =>
    staffOnly(`/zones/${enc(zoneId)}`, { method: "PATCH", body }),
  createZone: (canteenId: string, body: { name: string; capacity: number }): Promise<ZoneResult> =>
    staffOnly(`/canteens/${enc(canteenId)}/zones`, { method: "POST", body }),
  safetyActive: (): Promise<SafetyActive> =>
    either("/safety/active", (now) => ({ server_time: iso(now), ...safetyStatus(now) }), "Safety status unavailable"),
  safetyEvents: (status: "open" | "resolved" | "all"): Promise<StaffSafetyEventList> => staffOnly(`/safety/events?status=${status}`),
  safetySources: (): Promise<SafetySourceList> => staffOnly("/safety/sources"),
  acknowledgeSafety: (id: string, note: string | null): Promise<StaffSafetyEventResult> =>
    staffOnly(`/safety/events/${enc(id)}/acknowledge`, { method: "POST", body: { note } }),
  resolveSafety: (id: string, note: string): Promise<StaffSafetyEventResult> =>
    staffOnly(`/safety/events/${enc(id)}/resolve`, { method: "POST", body: { note } }),
  simulateSafety: (body: { event_type: string; canteen_id: string | null; note: string | null }): Promise<StaffSafetyEventResult> =>
    staffOnly("/safety/simulate", { method: "POST", body }),
  recommendation: (fromCanteen: string | null): Promise<RecommendationResult> =>
    either(
      fromCanteen ? `/recommendations?from_canteen=${enc(fromCanteen)}` : "/recommendations",
      (now) => sampleRecommendation(fromCanteen, now),
      "Recommendation unavailable",
    ),
  zoneHistory: (zoneId: string, from: string, bucket: HistoryBucket): Promise<ZoneHistory> =>
    staffOnly(`/zones/${enc(zoneId)}/occupancy/history?from=${enc(from)}&bucket=${bucket}`),
};
