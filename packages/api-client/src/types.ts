export type CrowdLevel = "normal" | "busy" | "crowded" | "near_capacity" | "unknown";
export type Freshness = "live" | "stale" | "unavailable";
export type MealPeriod = "breakfast" | "lunch" | "dinner";
export type FreeRange = [number, number];

export interface Timestamped {
  server_time: string;
}

export interface WalkTime {
  from_name: string;
  minutes: number;
}

export interface CanteenSummary {
  id: string;
  name: string;
  is_sample: boolean;
  level: CrowdLevel;
  freshness: Freshness;
  percent: number | null;
  free_about: number | null;
  free_range: FreeRange | null;
  monitored_capacity: number;
  zones_live: number;
  zones_total: number;
  shops_total: number;
  shops_open: number;
  walk: WalkTime | null;
  updated_at: string | null;
}

export type ShopState = "open" | "closes_soon" | "closed" | "temporarily_closed" | "unknown";

export interface ShopStatus {
  state: ShopState;
  closes_at_local: string | null;
  opens_at_local: string | null;
  reason: string | null;
}

export type ShopKind = "rice" | "kottu" | "short_eats" | "tea" | "noodles" | "bakery" | "drinks";

export interface Shop {
  id: string;
  name: string;
  canteen_id: string;
  canteen_name: string;
  kind: ShopKind;
  is_sample: boolean;
  status: ShopStatus;
  hours_label: string;
  menu_updated_at: string | null;
}

export type MenuTag = "rice" | "kottu" | "short_eats" | "drinks" | "vegetarian";

export interface MenuItem {
  id: string;
  name: string;
  price_lkr: number;
  tags: MenuTag[];
  periods: MealPeriod[];
  is_available: boolean;
}

export interface Menu extends Timestamped {
  shop_id: string;
  is_sample: boolean;
  items: MenuItem[];
  menu_updated_at: string | null;
}

export interface ShopList extends Timestamped {
  canteen_id: string;
  items: Shop[];
}

export interface BusyPoint {
  label: string;
  percent: number;
  is_forecast: boolean;
  is_now: boolean;
}

export interface SafetyEvent {
  id: string;
  event_type: string;
  title: string;
  canteen_name: string | null;
  occurred_at: string;
  is_simulation: boolean;
  status: "active" | "acknowledged" | "resolved";
  source_name: string;
  instructions: string;
}

export interface SafetyStatus {
  active: boolean;
  events: SafetyEvent[];
}

export interface StudentSummary extends Timestamped {
  best: { canteen_id: string; name: string } | null;
  canteens: CanteenSummary[];
  shops_now: Shop[];
  busy_today: { canteen_id: string; canteen_name: string; points: BusyPoint[] } | null;
  safety: SafetyStatus;
}

export interface ZoneOccupancy {
  zone_id: string;
  name: string;
  capacity: number;
  freshness: Freshness;
  level: CrowdLevel;
  percent: number | null;
  free_about: number | null;
  free_range: FreeRange | null;
  updated_at: string | null;
}

export interface ForecastPoint {
  at: string;
  low: number;
  high: number;
}

export interface OpeningHours {
  opens: string;
  closes: string;
}

export interface CanteenDetail extends Timestamped {
  canteen: CanteenSummary;
  hours_today: OpeningHours[];
  zones: ZoneOccupancy[];
  forecast: ForecastPoint[];
  shops: Shop[];
}

export interface MealWindow {
  period: MealPeriod;
  starts: string;
  ends: string;
}

export type WeekDayKind = "regular" | "special" | "closed";

export interface WeekDay {
  date: string;
  weekday: string;
  day: number;
  kind: WeekDayKind;
  note: string | null;
  is_today: boolean;
}

export interface MealStatus extends Timestamped {
  timezone: "Asia/Colombo";
  is_sample: boolean;
  state: "active" | "upcoming" | "none";
  current: MealWindow | null;
  next: MealWindow | null;
  today: MealWindow[];
  week: WeekDay[];
}

export type NoticeKind = "crowding" | "data_unavailable" | "sold_out" | "shop_closing" | "meal_starting";

export interface Notice {
  id: string;
  kind: NoticeKind;
  title: string;
  body: string;
  context: string;
  at: string;
  related_canteen: { id: string; name: string } | null;
}

export interface ErrorResponse {
  error: { code: string; message: string; details: Record<string, unknown> | null };
  request_id: string;
}

export interface AlertFeed extends Timestamped {
  safety: SafetyStatus;
  notices: Notice[];
}

export interface ConsoleZone {
  zone_id: string;
  name: string;
  canteen_name: string;
  capacity: number;
  freshness: Freshness;
  level: CrowdLevel;
  occupied: number | null;
  occupied_range: FreeRange | null;
  updated_at: string | null;
}

export type StaffAlertType = "crowding" | "sensor_offline" | "data_stale";
export type StaffAlertStatus = "open" | "acknowledged" | "suspended" | "resolved";

export interface StaffAlert {
  id: string;
  type: StaffAlertType;
  level: CrowdLevel | null;
  title: string;
  detail: string | null;
  status: StaffAlertStatus;
  opened_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
}

export type DeviceStatus = "ok" | "not_reporting" | "offline";

export interface DeviceHealth {
  id: string;
  where: string;
  status: DeviceStatus;
  fps: number | null;
  latency_ms: number | null;
  last_seen_at: string | null;
}

export interface OccupancyPoint {
  at: string;
  percent: number;
  is_forecast: boolean;
}

export interface ConsoleOverview extends Timestamped {
  is_sample: boolean;
  zones: ConsoleZone[];
  alerts: StaffAlert[];
  devices: DeviceHealth[];
  occupancy_today: { canteen_name: string; points: OccupancyPoint[] };
  safety: {
    simulation_mode: boolean;
    events: SafetyEvent[];
    source: { name: string; online: boolean; last_heartbeat_at: string | null };
    real_integration_connected: boolean;
  };
}

export type StaffRole = "shop_manager" | "canteen_manager" | "campus_admin" | "safety_officer";

export interface StaffUser {
  id: string;
  email: string;
  display_name: string;
  role: StaffRole;
  canteen_ids: string[];
  shop_ids: string[];
}

export interface StaffSession {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: StaffUser;
}

export type MenuCategory = "rice" | "kottu" | "short_eats" | "drinks";
export type PendingChange = "none" | "new" | "edit" | "delete";

export interface MenuItemFields {
  name: string;
  price_lkr: number;
  category: MenuCategory | null;
  dietary_tags: "vegetarian"[];
  periods: MealPeriod[];
}

export interface EditableMenuItem {
  id: string;
  live: MenuItemFields | null;
  draft: MenuItemFields | null;
  pending: PendingChange;
  is_available: boolean;
  availability_updated_at: string;
}

export interface WeeklyHours {
  weekday: number;
  opens: string;
  closes: string;
}

export interface HoursException {
  date: string;
  is_closed: boolean;
  opens: string | null;
  closes: string | null;
  reason: string | null;
}

export interface ManagedShop {
  shop: Shop;
  pending_changes: number;
}

export interface ManagedShopList extends Timestamped {
  items: ManagedShop[];
}

export interface ShopEditor extends Timestamped {
  shop: Shop;
  weekly: WeeklyHours[];
  exceptions: HoursException[];
  temporarily_closed_until: string | null;
  closure_reason: string | null;
  items: EditableMenuItem[];
  pending_changes: number;
}

export interface AvailabilityResult extends Timestamped {
  item: EditableMenuItem;
}
