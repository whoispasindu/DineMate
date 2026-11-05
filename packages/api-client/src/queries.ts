import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { serverNow } from "./clock";
import type { HistoryBucket, DeviceLayout, ShopEditor, StaffSafetyEventResult, ThresholdList, ThresholdValues } from "./types";

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
