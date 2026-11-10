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

export type StaffRole = "shop_manager" | "canteen_manager" | "campus_admin" | "safety_officer" | "owner" | "venue_manager";

export const BUSINESS_ROLES: readonly StaffRole[] = ["owner", "venue_manager"];

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

export interface MealSlot {
  weekday: number;
  period: MealPeriod;
  starts: string;
  ends: string;
}

export interface MealOverride {
  date: string;
  period: MealPeriod | null;
  is_cancelled: boolean;
  starts: string | null;
  ends: string | null;
  reason: string | null;
}

export interface MealScheduleSet extends Timestamped {
  canteen_id: string | null;
  canteen_name: string;
  uses_campus_weekly: boolean;
  weekly: MealSlot[];
  campus_weekly: MealSlot[];
  overrides: MealOverride[];
  can_edit: boolean;
}

export type AlertFrom = "busy" | "crowded" | "near_capacity";

export interface ThresholdValues {
  busy_pct: number;
  crowded_pct: number;
  near_capacity_pct: number;
  hysteresis_pct: number;
  dwell_seconds: number;
  alert_from: AlertFrom;
}

export interface ZoneThresholds {
  zone_id: string;
  zone_name: string;
  canteen_id: string;
  canteen_name: string;
  capacity: number;
  is_monitored: boolean;
  is_default: boolean;
  values: ThresholdValues;
}

export interface ThresholdList extends Timestamped {
  defaults: ThresholdValues;
  items: ZoneThresholds[];
}

export interface ThresholdResult extends Timestamped {
  item: ZoneThresholds;
}

export type PolygonType = "seating" | "queue" | "walkway" | "ignore" | "work";
export type WorkAreaName = "counter" | "kitchen" | "floor";

export interface LayoutSeat {
  seat_id: string;
  x: number;
  y: number;
}

export interface LayoutPolygon {
  type: PolygonType;
  zone_id: string | null;
  area?: WorkAreaName | null;
  points: [number, number][];
  seats?: LayoutSeat[];
}

export interface EditableZone {
  id: string;
  name: string;
  capacity: number;
  is_active: boolean;
  is_monitored: boolean;
}

export interface LayoutVersion {
  version: number;
  created_at: string;
  is_current: boolean;
  seating_zones: number;
}

export interface DeviceLayout extends Timestamped {
  device_id: string;
  canteen_id: string;
  canteen_name: string;
  kind: "camera" | "simulator";
  version: number | null;
  polygons: LayoutPolygon[];
  zones: EditableZone[];
  history: LayoutVersion[];
}

export interface ManagedDevice {
  id: string;
  kind: "camera" | "simulator";
  canteen_id: string;
  canteen_name: string;
  layout_version: number | null;
  last_heartbeat_at: string | null;
  is_enabled: boolean;
  label?: string | null;
}

export interface ManagedDeviceList extends Timestamped {
  items: ManagedDevice[];
}

export interface ZoneResult extends Timestamped {
  zone: EditableZone;
}

export type SafetyEventType = "fire_alarm" | "evacuation" | "test_notice" | "integration_offline";
export type SafetySeverity = "critical" | "warning" | "info";

export interface SafetyActive extends Timestamped {
  active: boolean;
  events: SafetyEvent[];
}

export interface SafetyAck {
  user_name: string;
  acknowledged_at: string;
  note: string | null;
}

export interface StaffSafetyEvent {
  id: string;
  event_type: SafetyEventType;
  title: string;
  severity: SafetySeverity;
  status: "active" | "acknowledged" | "resolved";
  is_simulation: boolean;
  label: string | null;
  canteen_id: string | null;
  canteen_name: string | null;
  zone_name: string | null;
  source_id: string;
  source_name: string;
  source_kind: "simulator" | "approved_integration";
  occurred_at: string;
  received_at: string;
  last_seen_at: string;
  repeat_count: number;
  note: string | null;
  instructions: string;
  acks: SafetyAck[];
  resolved_by_name: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
}

export interface StaffSafetyEventList extends Timestamped {
  simulation_mode: boolean;
  items: StaffSafetyEvent[];
}

export interface StaffSafetyEventResult extends Timestamped {
  event: StaffSafetyEvent;
}

export interface SafetySourceHealth {
  id: string;
  name: string;
  kind: "simulator" | "approved_integration";
  is_enabled: boolean;
  last_heartbeat_at: string | null;
  state: "online" | "offline" | "never_connected";
}

export interface SafetySourceList extends Timestamped {
  items: SafetySourceHealth[];
}

export type HistoryBucket = "5m" | "10m" | "15m" | "1h";

export interface ZoneHistoryPoint {
  t: string;
  mean: number;
  low: number;
  high: number;
  samples: number;
}

export interface ZoneHistory extends Timestamped {
  zone_id: string;
  zone_name: string;
  canteen_id: string;
  capacity: number;
  bucket: HistoryBucket;
  is_simulated: boolean;
  points: ZoneHistoryPoint[];
}

export interface Recommendation {
  canteen_id: string;
  name: string;
  level: CrowdLevel;
  free_about: number | null;
  available_range: FreeRange;
  walk_minutes: number | null;
  reason: string;
}

export interface RecommendationResult extends Timestamped {
  from_canteen_id: string | null;
  recommendation: Recommendation | null;
  message: string | null;
  excluded: { canteen_id: string; name: string; reason: "no_live_data" | "too_crowded" }[];
}

export type SeatStateName = "free" | "occupied" | "held" | "unknown";

export interface ZoneSeats {
  zone_id: string;
  name: string;
  freshness: Freshness;
  seats: number;
  free: number | null;
  occupied: number | null;
  held: number | null;
  unknown: number | null;
  free_soon: number | null;
  standing: number | null;
  crowded: boolean;
  updated_at: string | null;
}

export interface CanteenSeats extends Timestamped {
  canteen_id: string;
  zones: ZoneSeats[];
  held: number;
  free_soon: number;
  crowded_zones: number;
}

export interface CanteenSeatTotals {
  canteen_id: string;
  zones_with_seats: number;
  held: number;
  free_soon: number;
  crowded_zones: number;
}

export interface SeatOverview extends Timestamped {
  items: CanteenSeatTotals[];
}

export interface SeatDetail {
  seat_id: string;
  x: number;
  y: number;
  state: SeatStateName;
  since: string | null;
  free_soon: boolean;
}

export interface ZoneSeatMap extends Timestamped {
  zone_id: string;
  name: string;
  freshness: Freshness;
  seats: SeatDetail[];
}

export interface StayHour {
  hour: number;
  median_minutes: number;
  sessions: number;
}

export interface StayTimes extends Timestamped {
  canteen_id: string;
  days: number;
  sessions: number;
  median_minutes: number | null;
  hours: StayHour[];
  occupied_now: number;
  likely_free_10min: number | null;
  is_experimental: boolean;
}

export type TableStateName = "free" | "occupied" | "held" | "needs_clearing" | "unknown";
export type TableShape = "round" | "rect";

export interface VenueZone {
  id: string;
  name: string;
}

export interface VenueSummary {
  id: string;
  name: string;
  organization_name: string;
  is_sample: boolean;
  zones: VenueZone[];
  tables: number;
}

export interface VenueList extends Timestamped {
  items: VenueSummary[];
}

export interface LeaveEstimate {
  low_min: number;
  high_min: number;
}

export interface FloorTable {
  id: string;
  name: string;
  zone_id: string;
  zone_name: string;
  shape: TableShape;
  x: number;
  y: number;
  w: number;
  h: number;
  seats: number;
  state: TableStateName;
  party_size: number;
  since: string | null;
  seated_min: number | null;
  plates_left: boolean;
  estimate: LeaveEstimate | null;
}

export interface FloorTotals {
  tables: number;
  free: number;
  guests_seated: number;
  visits_today: number;
  avg_stay_today_min: number | null;
  turns_today: number;
  counter_staff?: number | null;
  queue_people?: number | null;
}

export interface VenueFloor extends Timestamped {
  venue_id: string;
  venue_name: string;
  is_sample: boolean;
  updated_at: string | null;
  totals: FloorTotals;
  tables: FloorTable[];
}

export interface HourCount {
  hour: number;
  visits: number;
}

export interface TableStay {
  table_id: string;
  name: string;
  seats: number;
  avg_stay_min: number | null;
  turns: number;
}

export interface CustomerDay extends Timestamped {
  venue_id: string;
  day: string;
  is_sample: boolean;
  visits: number;
  visits_last_week: number;
  guests: number;
  avg_stay_min: number | null;
  median_stay_min: number | null;
  turns_per_table: number;
  by_hour: HourCount[];
  by_table: TableStay[];
}

export interface DayTotal {
  day: string;
  visits: number;
  guests: number;
  avg_stay_min: number | null;
}

export interface HeatCell {
  weekday: number;
  hour: number;
  visits: number;
}

export type ReportRange = "day" | "week";

export interface VenueReport extends Timestamped {
  venue_id: string;
  range: ReportRange;
  is_sample: boolean;
  days: DayTotal[];
  heat: HeatCell[];
  heat_days: number;
}

export interface CameraHealth {
  id: string;
  kind: "camera" | "simulator";
  zones: string[];
  status: "ok" | "not_reporting" | "offline";
  fps: number | null;
  last_seen_at: string | null;
  label?: string | null;
  source_hint?: string | null;
  has_layout?: boolean;
  waiting_for_zones?: boolean;
  detail?: CameraDetail;
}

export type CameraDetail = "auto" | "standard" | "high";

export interface CameraIn {
  label: string;
  source: string;
  detail?: CameraDetail;
}

export interface CameraPatch {
  label?: string;
  source?: string;
  enabled?: boolean;
  detail?: CameraDetail;
}

export interface CameraOut {
  id: string;
  venue_id: string;
  label: string;
  source_hint: string | null;
  enabled: boolean;
  detail?: CameraDetail;
}

export interface CameraResult extends Timestamped {
  camera: CameraOut;
}

export interface CameraRemoved extends Timestamped {
  device_id: string;
}

export interface AreaResult extends Timestamped {
  zone: EditableZone;
}

export interface UploadedVideo extends Timestamped {
  source: string;
  name: string;
  size_mb: number;
}

export interface VideoFeedIn {
  label: string;
  source: string;
  detail?: CameraDetail;
}

export interface VideoFeed {
  id: string;
  canteen_id: string;
  canteen_name: string;
  label: string;
  source_hint: string | null;
  status: "ok" | "waiting_for_zones" | "starting" | "offline";
  last_seen_at: string | null;
  fps: number | null;
  zones: string[];
  has_layout: boolean;
  detail?: CameraDetail;
}

export interface VideoFeedList extends Timestamped {
  items: VideoFeed[];
  max_feeds: number;
}

export interface VideoFeedResult extends Timestamped {
  feed: VideoFeed;
}

export interface VideoFeedRemoved extends Timestamped {
  device_id: string;
}

export interface VenueCameras extends Timestamped {
  venue_id: string;
  items: CameraHealth[];
}

export interface SeatPoint {
  seat_id: string;
  x: number;
  y: number;
}

export interface LayoutZoneSeats {
  zone_id: string;
  name: string;
  seats: SeatPoint[];
}

export interface TableFields {
  name: string;
  zone_id: string;
  shape: TableShape;
  x: number;
  y: number;
  w: number;
  h: number;
  seat_ids: string[];
}

export interface TableOut extends TableFields {
  id: string;
}

export interface TableIn extends TableFields {
  id?: string | null;
}

export interface TableLayout extends Timestamped {
  venue_id: string;
  zones: LayoutZoneSeats[];
  tables: TableOut[];
}

export interface BusinessSettings extends Timestamped {
  organization_id: string;
  organization_name: string;
  retention_days: number;
  staff_retention_days: number;
  deployment: "local" | "cloud";
  faces_enabled: boolean;
}

export interface BusinessSettingsIn {
  retention_days?: number;
  staff_retention_days?: number;
}

export type StaffMethod = "face" | "badge";

export interface StaffMember {
  id: string;
  display_name: string;
  role_label: string;
  method: StaffMethod;
  badge_code: number | null;
  till_code: string | null;
  consent_at: string | null;
  consent_version: string | null;
  has_template: boolean;
  active: boolean;
  is_sample: boolean;
}

export interface StaffList extends Timestamped {
  venue_id: string;
  items: StaffMember[];
}

export interface StaffResult extends Timestamped {
  staff: StaffMember;
}

export interface StaffIn {
  display_name: string;
  role_label?: string;
  method?: StaffMethod;
  badge_code?: number | null;
  till_code?: string | null;
}

export interface StaffPatch extends Partial<StaffIn> {
  active?: boolean;
}

export interface ConsentIn {
  version: string;
  signed_on: string;
}

export interface StaffRemoved extends Timestamped {
  staff_id: string;
}

export interface TimeSpan {
  start: string;
  end: string;
}

export interface CoverageGap extends TimeSpan {
  minutes: number;
}

export interface QueueAlert extends TimeSpan {
  peak: number;
}

export interface CounterCoverage {
  open_min: number;
  covered_min: number;
  share: number | null;
  gaps: CoverageGap[];
}

export interface AreaMinutes {
  counter: number;
  kitchen: number;
  floor: number;
}

export interface ItemCount {
  name: string;
  qty: number;
}

export interface WorkerDay {
  staff_id: string;
  display_name: string;
  role_label: string;
  method: StaffMethod;
  first_seen: string | null;
  last_seen: string | null;
  minutes: AreaMinutes;
  orders: number;
  items: ItemCount[];
  total_items: number;
}

export interface StaffReport extends Timestamped {
  venue_id: string;
  day: string;
  is_sample: boolean;
  coverage: CounterCoverage;
  queue_alerts: QueueAlert[];
  workers: WorkerDay[];
}

export interface SheetDay {
  day: string;
  minutes: AreaMinutes;
  items: number;
}

export interface StaffSheet extends Timestamped {
  staff: StaffMember;
  venue_name: string;
  days: SheetDay[];
  kept_days: number;
}

export interface TillImportResult extends Timestamped {
  rows: number;
  orders: number;
  new_orders: number;
  duplicates: number;
  errors: string[];
  matched_cashiers: string[];
  unmatched_cashiers: string[];
  saved: boolean;
}

export interface CashierItems {
  cashier: string;
  staff_id: string | null;
  staff_name: string | null;
  items: ItemCount[];
  total_items: number;
  orders: number;
}

export interface HourOrders {
  hour: number;
  orders: number;
}

export interface SalesDay extends Timestamped {
  venue_id: string;
  day: string;
  is_sample: boolean;
  orders: number;
  items: number;
  revenue: number;
  average_order: number | null;
  by_hour: HourOrders[];
  by_cashier: CashierItems[];
  top_items: ItemCount[];
}

export interface LiveLink extends Timestamped {
  device_id: string;
  url: string;
  expires_at: string;
}

export interface AuditEntry {
  at: string;
  actor: string;
  action: string;
  entity_id: string;
}

export interface AuditList extends Timestamped {
  items: AuditEntry[];
}
