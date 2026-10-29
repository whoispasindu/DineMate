import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { ShopEditor } from "./types";

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
