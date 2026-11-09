import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { serverNow } from "./clock";
import type {
  CameraIn,
  CameraPatch,
  LayoutPolygon,
  BusinessSettingsIn,
  ConsentIn,
  StaffIn,
  StaffPatch,
  HistoryBucket,
  DeviceLayout,
  ReportRange,
  ShopEditor,
  StaffSafetyEventResult,
  TableIn,
  ThresholdList,
  ThresholdValues,
} from "./types";

const LIVE_POLL_MS = 15_000;
const INFO_POLL_MS = 60_000;

export const queryKeys = {
  summary: ["student", "summary"] as const,
  canteens: ["canteens"] as const,
  canteen: (id: string) => ["canteen", id] as const,
  shops: (canteenId: string) => ["shops", canteenId] as const,
  menu: (shopId: string) => ["menu", shopId] as const,
  mealStatus: ["meal-status"] as const,
  alerts: ["alerts"] as const,
  consoleOverview: ["console", "overview"] as const,
  managedShops: ["manage", "shops"] as const,
  shopEditor: (shopId: string) => ["manage", "shop", shopId] as const,
  mealSchedules: (canteenId: string | null) => ["manage", "meal-schedules", canteenId ?? "campus"] as const,
  thresholds: ["manage", "thresholds"] as const,
  managedDevices: ["manage", "devices"] as const,
  deviceLayout: (deviceId: string) => ["manage", "layout", deviceId] as const,
  safetyActive: ["safety", "active"] as const,
  safetyEvents: (status: string) => ["safety", "events", status] as const,
  safetySources: ["safety", "sources"] as const,
  recommendation: (fromCanteen: string | null) => ["recommendation", fromCanteen ?? "any"] as const,
  zoneHistory: (zoneId: string, hours: number, bucket: string) => ["zone-history", zoneId, hours, bucket] as const,
  canteenSeats: (canteenId: string) => ["seats", canteenId] as const,
  seatOverview: ["seats", "overview"] as const,
  zoneSeatMap: (zoneId: string) => ["seats", "zone", zoneId] as const,
  stayTimes: (canteenId: string) => ["seats", "stays", canteenId] as const,
  venues: ["business", "venues"] as const,
  floor: (venueId: string) => ["business", "floor", venueId] as const,
  customers: (venueId: string, day: string) => ["business", "customers", venueId, day] as const,
  report: (venueId: string, range: string) => ["business", "report", venueId, range] as const,
  cameras: (venueId: string) => ["business", "cameras", venueId] as const,
  tables: (venueId: string) => ["business", "tables", venueId] as const,
  businessSettings: ["business", "settings"] as const,
  staff: (venueId: string) => ["business", "staff", venueId] as const,
  staffReport: (venueId: string, day: string) => ["business", "staff-report", venueId, day] as const,
  staffSheet: (staffId: string) => ["business", "staff-sheet", staffId] as const,
  staffAudit: ["business", "audit"] as const,
  sales: (venueId: string, day: string) => ["business", "sales", venueId, day] as const,
  liveLink: (venueId: string, deviceId: string) => ["business", "live", venueId, deviceId] as const,
  cameraLayout: (deviceId: string) => ["business", "camera-layout", deviceId] as const,
};

export function useStudentSummary() {
  return useQuery({ queryKey: queryKeys.summary, queryFn: api.studentSummary, refetchInterval: LIVE_POLL_MS });
}

export function useCanteens() {
  return useQuery({ queryKey: queryKeys.canteens, queryFn: api.canteens, staleTime: Infinity });
}

export function useCanteen(id: string) {
  return useQuery({ queryKey: queryKeys.canteen(id), queryFn: () => api.canteen(id), refetchInterval: LIVE_POLL_MS, retry: false });
}

export function useShops(canteenId: string) {
  return useQuery({ queryKey: queryKeys.shops(canteenId), queryFn: () => api.shops(canteenId), refetchInterval: INFO_POLL_MS });
}

export function useMenu(shopId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.menu(shopId ?? ""),
    queryFn: () => api.menu(shopId ?? ""),
    enabled: shopId !== undefined,
    refetchInterval: INFO_POLL_MS,
  });
}

export function useMealStatus() {
  return useQuery({ queryKey: queryKeys.mealStatus, queryFn: api.mealStatus, refetchInterval: INFO_POLL_MS });
}

export function useAlertFeed() {
  return useQuery({ queryKey: queryKeys.alerts, queryFn: api.alerts, refetchInterval: LIVE_POLL_MS });
}

export function useConsoleOverview(enabled = true) {
  return useQuery({ queryKey: queryKeys.consoleOverview, queryFn: api.consoleOverview, refetchInterval: LIVE_POLL_MS, enabled });
}

export function useAcknowledgeAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.acknowledgeAlert,
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.consoleOverview }),
  });
}

export function useManagedShops() {
  return useQuery({ queryKey: queryKeys.managedShops, queryFn: api.managedShops, retry: false });
}

export function useShopEditor(shopId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.shopEditor(shopId ?? ""),
    queryFn: () => api.shopEditor(shopId ?? ""),
    enabled: shopId !== undefined,
    retry: false,
  });
}

export function useShopMutation<A>(shopId: string, run: (arg: A) => Promise<ShopEditor>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (editor) => {
      client.setQueryData(queryKeys.shopEditor(shopId), editor);
      void client.invalidateQueries({ queryKey: queryKeys.managedShops });
      void client.invalidateQueries({ queryKey: queryKeys.menu(shopId) });
    },
  });
}

export function useSetAvailability(shopId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, isAvailable }: { itemId: string; isAvailable: boolean }) => api.setAvailability(itemId, isAvailable),
    onSuccess: ({ item }) => {
      client.setQueryData<ShopEditor>(queryKeys.shopEditor(shopId), (old) =>
        old ? { ...old, items: old.items.map((i) => (i.id === item.id ? item : i)) } : old,
      );
      void client.invalidateQueries({ queryKey: queryKeys.menu(shopId) });
    },
  });
}

export function useMealSchedules(canteenId: string | null) {
  return useQuery({ queryKey: queryKeys.mealSchedules(canteenId), queryFn: () => api.mealSchedules(canteenId), retry: false });
}

export function useSaveMealSchedules() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.saveMealSchedules,
    onSuccess: (set) => {
      client.setQueryData(queryKeys.mealSchedules(set.canteen_id), set);
      void client.invalidateQueries({ queryKey: queryKeys.mealStatus });
    },
  });
}

export function useThresholds() {
  return useQuery({ queryKey: queryKeys.thresholds, queryFn: api.thresholds, retry: false });
}

export function useSaveThresholds() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ zoneId, values }: { zoneId: string; values: ThresholdValues }) => api.saveThresholds(zoneId, values),
    onSuccess: ({ item }) =>
      client.setQueryData<ThresholdList>(queryKeys.thresholds, (old) =>
        old ? { ...old, items: old.items.map((z) => (z.zone_id === item.zone_id ? item : z)) } : old,
      ),
  });
}

export function useManagedDevices() {
  return useQuery({ queryKey: queryKeys.managedDevices, queryFn: api.managedDevices, retry: false });
}

export function useDeviceLayout(deviceId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.deviceLayout(deviceId ?? ""),
    queryFn: () => api.deviceLayout(deviceId ?? ""),
    enabled: deviceId !== undefined,
    retry: false,
  });
}

export function useLayoutMutation<A>(deviceId: string, run: (arg: A) => Promise<DeviceLayout>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (layout) => {
      client.setQueryData(queryKeys.deviceLayout(deviceId), layout);
      void client.invalidateQueries({ queryKey: queryKeys.managedDevices });
    },
  });
}

const SAFETY_POLL_MS = 10_000;
const SAFETY_DESK_POLL_MS = 5_000;

export function useSafetyActive() {
  return useQuery({ queryKey: queryKeys.safetyActive, queryFn: api.safetyActive, refetchInterval: SAFETY_POLL_MS, retry: false });
}

export function useSafetyEvents(status: "open" | "resolved" | "all") {
  return useQuery({
    queryKey: queryKeys.safetyEvents(status),
    queryFn: () => api.safetyEvents(status),
    refetchInterval: SAFETY_DESK_POLL_MS,
    retry: false,
  });
}

export function useSafetySources() {
  return useQuery({ queryKey: queryKeys.safetySources, queryFn: api.safetySources, refetchInterval: 15_000, retry: false });
}

export function useSafetyAction<A>(run: (arg: A) => Promise<StaffSafetyEventResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["safety"] });
      void client.invalidateQueries({ queryKey: queryKeys.consoleOverview });
    },
  });
}

export function useRecommendation(fromCanteen: string | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.recommendation(fromCanteen),
    queryFn: () => api.recommendation(fromCanteen),
    refetchInterval: LIVE_POLL_MS,
    enabled,
  });
}

export function useZoneHistory(zoneId: string | undefined, hours: number, bucket: HistoryBucket) {
  return useQuery({
    queryKey: queryKeys.zoneHistory(zoneId ?? "", hours, bucket),
    queryFn: () => api.zoneHistory(zoneId ?? "", new Date(serverNow() - hours * 3_600_000).toISOString(), bucket),
    enabled: zoneId !== undefined,
    refetchInterval: 60_000,
    retry: false,
  });
}

export function useCanteenSeats(canteenId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.canteenSeats(canteenId ?? ""),
    queryFn: () => api.canteenSeats(canteenId ?? ""),
    enabled: canteenId !== undefined,
    refetchInterval: LIVE_POLL_MS,
    retry: false,
  });
}

export function useSeatOverview() {
  return useQuery({
    queryKey: queryKeys.seatOverview,
    queryFn: api.seatOverview,
    refetchInterval: LIVE_POLL_MS,
    retry: false,
  });
}

export function useZoneSeatMap(zoneId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.zoneSeatMap(zoneId ?? ""),
    queryFn: () => api.zoneSeatMap(zoneId ?? ""),
    enabled: zoneId !== undefined,
    refetchInterval: LIVE_POLL_MS,
    retry: false,
  });
}

export function useStayTimes(canteenId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.stayTimes(canteenId ?? ""),
    queryFn: () => api.stayTimes(canteenId ?? ""),
    enabled: canteenId !== undefined,
    refetchInterval: INFO_POLL_MS,
    retry: false,
  });
}

const FLOOR_POLL_MS = 10_000;

export function useVenues(enabled = true) {
  return useQuery({ queryKey: queryKeys.venues, queryFn: api.businessVenues, enabled, retry: false });
}

export function useFloor(venueId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.floor(venueId ?? ""),
    queryFn: () => api.businessFloor(venueId ?? ""),
    enabled: venueId !== undefined,
    refetchInterval: FLOOR_POLL_MS,
    retry: false,
  });
}

export function useCustomers(venueId: string | undefined, day?: string) {
  return useQuery({
    queryKey: queryKeys.customers(venueId ?? "", day ?? "today"),
    queryFn: () => api.businessCustomers(venueId ?? "", day),
    enabled: venueId !== undefined,
    refetchInterval: INFO_POLL_MS,
    retry: false,
  });
}

export function useReport(venueId: string | undefined, range: ReportRange) {
  return useQuery({
    queryKey: queryKeys.report(venueId ?? "", range),
    queryFn: () => api.businessReport(venueId ?? "", range),
    enabled: venueId !== undefined,
    refetchInterval: INFO_POLL_MS,
    retry: false,
  });
}

export function useCameras(venueId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cameras(venueId ?? ""),
    queryFn: () => api.businessCameras(venueId ?? ""),
    enabled: venueId !== undefined,
    refetchInterval: LIVE_POLL_MS,
    retry: false,
  });
}

export function useTableLayout(venueId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.tables(venueId ?? ""),
    queryFn: () => api.businessTables(venueId ?? ""),
    enabled: venueId !== undefined,
    retry: false,
  });
}

export function useSaveTables(venueId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (tables: TableIn[]) => api.saveBusinessTables(venueId, tables),
    onSuccess: (layout) => {
      client.setQueryData(queryKeys.tables(venueId), layout);
      void client.invalidateQueries({ queryKey: queryKeys.floor(venueId) });
      void client.invalidateQueries({ queryKey: queryKeys.venues });
    },
  });
}

export function useMarkCleared(venueId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (tableId: string) => api.markTableCleared(tableId),
    onSuccess: (floor) => client.setQueryData(queryKeys.floor(venueId), floor),
  });
}

export function useBusinessSettings() {
  return useQuery({ queryKey: queryKeys.businessSettings, queryFn: api.businessSettings, retry: false });
}

export function useSaveBusinessSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: BusinessSettingsIn) => api.saveBusinessSettings(body),
    onSuccess: (settings) => client.setQueryData(queryKeys.businessSettings, settings),
  });
}

export function useStaff(venueId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.staff(venueId ?? ""),
    queryFn: () => api.businessStaff(venueId ?? ""),
    enabled: enabled && venueId !== undefined,
    retry: false,
  });
}

function useStaffChange<A>(venueId: string, run: (args: A) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.staff(venueId) });
      void client.invalidateQueries({ queryKey: ["business", "staff-report", venueId] });
      void client.invalidateQueries({ queryKey: queryKeys.staffAudit });
    },
  });
}

export function useCreateStaff(venueId: string) {
  return useStaffChange(venueId, (body: StaffIn) => api.createStaff(venueId, body));
}

export function useUpdateStaff(venueId: string) {
  return useStaffChange(venueId, ({ staffId, body }: { staffId: string; body: StaffPatch }) => api.updateStaff(staffId, body));
}

export function useRecordConsent(venueId: string) {
  return useStaffChange(venueId, ({ staffId, body }: { staffId: string; body: ConsentIn }) => api.recordConsent(staffId, body));
}

export function useWithdrawConsent(venueId: string) {
  return useStaffChange(venueId, (staffId: string) => api.withdrawConsent(staffId));
}

export function useRemoveStaff(venueId: string) {
  return useStaffChange(venueId, (staffId: string) => api.removeStaff(staffId));
}

export function useStaffReport(venueId: string | undefined, day?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.staffReport(venueId ?? "", day ?? "today"),
    queryFn: () => api.staffReport(venueId ?? "", day),
    enabled: enabled && venueId !== undefined,
    refetchInterval: INFO_POLL_MS,
    retry: false,
  });
}

export function useStaffSheet(staffId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.staffSheet(staffId ?? ""),
    queryFn: () => api.staffSheet(staffId ?? ""),
    enabled: staffId !== undefined,
    retry: false,
  });
}

export function useStaffAudit(enabled = true) {
  return useQuery({ queryKey: queryKeys.staffAudit, queryFn: api.staffAudit, enabled, retry: false });
}

export function useSales(venueId: string | undefined, day?: string) {
  return useQuery({
    queryKey: queryKeys.sales(venueId ?? "", day ?? "today"),
    queryFn: () => api.sales(venueId ?? "", day),
    enabled: venueId !== undefined,
    refetchInterval: INFO_POLL_MS,
    retry: false,
  });
}

export function useImportTill(venueId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ csv, dryRun }: { csv: string; dryRun: boolean }) => api.importTill(venueId, csv, dryRun),
    onSuccess: (result) => {
      if (!result.saved) return;
      void client.invalidateQueries({ queryKey: ["business", "sales", venueId] });
      void client.invalidateQueries({ queryKey: ["business", "staff-report", venueId] });
    },
  });
}

export function useLiveLink(venueId: string | undefined, deviceId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.liveLink(venueId ?? "", deviceId ?? ""),
    queryFn: () => api.liveLink(venueId ?? "", deviceId ?? ""),
    enabled: venueId !== undefined && deviceId !== undefined,
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

function useCameraChange<A, R>(venueId: string, run: (args: A) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.cameras(venueId) });
      void client.invalidateQueries({ queryKey: queryKeys.venues });
    },
  });
}

export function useAddCamera(venueId: string) {
  return useCameraChange(venueId, (body: CameraIn) => api.addCamera(venueId, body));
}

export function useUpdateCamera(venueId: string) {
  return useCameraChange(venueId, ({ deviceId, body }: { deviceId: string; body: CameraPatch }) => api.updateCamera(deviceId, body));
}

export function useRemoveCamera(venueId: string) {
  return useCameraChange(venueId, (deviceId: string) => api.removeCamera(deviceId));
}

export function useCameraLayout(deviceId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cameraLayout(deviceId ?? ""),
    queryFn: () => api.cameraLayout(deviceId ?? ""),
    enabled: deviceId !== undefined,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useSaveCameraLayout(venueId: string, deviceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { base_version: number | null; polygons: LayoutPolygon[] }) => api.saveCameraLayout(deviceId, body),
    onSuccess: (layout) => {
      client.setQueryData(queryKeys.cameraLayout(deviceId), layout);
      void client.invalidateQueries({ queryKey: queryKeys.cameras(venueId) });
      void client.invalidateQueries({ queryKey: queryKeys.tables(venueId) });
    },
  });
}

export function useAddArea(venueId: string, deviceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.addArea(venueId, name),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.cameraLayout(deviceId) }),
  });
}
