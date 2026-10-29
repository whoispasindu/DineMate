import {
  useCanteens,
  useMealStatus,
  useMenu,
  useShops,
  type MealPeriod,
  type MenuItem,
  type MenuTag,
  type Shop,
} from "@dinemate/api-client";
import { cx, FoodArt, foodArtFor, formatClock, formatPrice, SampleBadge, shopArtFor } from "@dinemate/ui";
import { useId, useState } from "react";
import { Link, useSearchParams } from "react-router";
import {
  CanteenSelect,
  FilterChips,
  Footnote,
  Loading,
  MessageCard,
  SearchField,
  Segmented,
  ShopStatusDot,
  Skeleton,
} from "../components/common";
import { useIsDesktop } from "../lib/device";
import { PERIOD_LABEL, PERIODS } from "../lib/present";

type Category = "all" | MenuTag;

const CATEGORIES: { value: Category; label: string }[] = [
  { value: "all", label: "All" },
  { value: "rice", label: "Rice & curry" },
  { value: "kottu", label: "Kottu" },
  { value: "short_eats", label: "Short eats" },
  { value: "drinks", label: "Drinks" },
  { value: "vegetarian", label: "Vegetarian" },
];

const PERIOD_OPTIONS = PERIODS.map((p) => ({ value: p, label: PERIOD_LABEL[p] }));

function ItemArt({ item, className, fit }: { item: MenuItem; className: string; fit?: "cover" | "contain" }) {
  return <FoodArt kind={foodArtFor(item.name, item.tags)} name={item.name} muted={!item.is_available} className={className} fit={fit} />;
}

function ShopArt({ shop, className }: { shop: Shop; className: string }) {
  return <FoodArt kind={shopArtFor(shop.kind)} name={shop.name} className={className} />;
}

function defaultShop(shops: Shop[]): Shop | undefined {
  return shops.find((s) => s.status.state === "open" || s.status.state === "closes_soon") ?? shops[0];
}

export function FoodScreen() {
  const isDesktop = useIsDesktop();
  const [params, setParams] = useSearchParams();
  const canteens = useCanteens();
  const canteenId = params.get("canteen") ?? canteens.data?.items[0]?.id ?? "a";
  const shops = useShops(canteenId);
  const shopList = shops.data?.items ?? [];
  const requested = params.get("shop");
  const shop = shopList.find((s) => s.id === requested) ?? defaultShop(shopList);
  const menu = useMenu(shop?.id);
  const meal = useMealStatus();
  const [period, setPeriod] = useState<MealPeriod | null>(null);
  const [q, setQ] = useState(params.get("q") ?? "");
  const [category, setCategory] = useState<Category>("all");
  const panelId = useId();

  const activePeriod = period ?? meal.data?.current?.period ?? meal.data?.next?.period ?? "lunch";
  const needle = q.trim().toLowerCase();
  const allItems = menu.data?.items ?? [];
  const items = allItems.filter(
    (item) =>
      item.periods.includes(activePeriod) &&
      (category === "all" || item.tags.includes(category)) &&
      (needle === "" || item.name.toLowerCase().includes(needle)),
  );
  const filtering = needle !== "" || category !== "all";

  const selectCanteen = (id: string) => setParams({ canteen: id }, { replace: true });
  const shopHref = (s: Shop) => `?canteen=${canteenId}&shop=${s.id}`;

  const view: FoodViewProps = {
    canteenId,
    canteens: canteens.data?.items ?? [],
    selectCanteen,
    shops: shopList,
    shopsLoading: shops.isPending,
    shop,
    shopHref,
    q,
    setQ,
    category,
    setCategory,
    period: activePeriod,
    setPeriod,
    panelId,
    items,
    menuLoading: shop !== undefined && menu.isPending,
    menuEmpty: menu.data !== undefined && allItems.length === 0,
    filtering,
    menuUpdatedAt: menu.data?.menu_updated_at ?? null,
    isSample: menu.data?.is_sample ?? shop?.is_sample ?? true,
  };
  return isDesktop ? <FoodWeb {...view} /> : <FoodMobile {...view} />;
}

interface FoodViewProps {
  canteenId: string;
  canteens: { id: string; name: string }[];
  selectCanteen: (id: string) => void;
  shops: Shop[];
  shopsLoading: boolean;
  shop: Shop | undefined;
  shopHref: (shop: Shop) => string;
  q: string;
  setQ: (q: string) => void;
  category: Category;
  setCategory: (c: Category) => void;
  period: MealPeriod;
  setPeriod: (p: MealPeriod) => void;
  panelId: string;
  items: MenuItem[];
  menuLoading: boolean;
  menuEmpty: boolean;
  filtering: boolean;
  menuUpdatedAt: string | null;
  isSample: boolean;
}

function MenuEmpty({ menuEmpty, filtering, period }: Pick<FoodViewProps, "menuEmpty" | "filtering" | "period">) {
  if (menuEmpty) return <MessageCard icon="utensils" dashed title="Menu not added yet" body="This shop hasn't published a menu." />;
  if (filtering) return <MessageCard icon="search" title="Nothing matches" body="Try another search or category." />;
  return (
    <MessageCard
      icon="utensils"
      dashed
      title={`No ${PERIOD_LABEL[period].toLowerCase()} menu`}
      body="This shop doesn't list items for this meal."
    />
  );
}

function AvailabilityChip({ available }: { available: boolean }) {
  return (
    <span
      className={cx(
        "shrink-0 rounded-full px-[9px] py-[3px] text-[11px] font-extrabold md:py-[3px]",
        available ? "bg-ok-bg text-ok" : "border border-dashed border-dash bg-neutral text-neutral-ink",
      )}
    >
      {available ? "Available" : "Sold out"}
    </span>
  );
}

function ShopCard({ shop, href, selected }: { shop: Shop; href: string; selected: boolean }) {
  return (
    <Link
      to={href}
      replace
      aria-current={selected ? "true" : undefined}
      className={cx(
        "flex min-w-[85%] shrink-0 snap-start items-center gap-3 rounded-[18px] border p-3.5 text-ink no-underline",
        selected ? "border-mint-line bg-card" : "border-line bg-card opacity-80",
      )}
    >
      <ShopArt shop={shop} className="h-12 w-12 shrink-0 rounded-[14px]" />
      <span className="flex flex-1 flex-col gap-[3px]">
        <span className="text-base font-extrabold">{shop.name}</span>
        <ShopStatusDot status={shop.status} />
      </span>
      {shop.is_sample ? <SampleBadge className="px-[7px] text-[10px]">SAMPLE</SampleBadge> : null}
    </Link>
  );
}

function FoodMobile(props: FoodViewProps) {
  const { canteenId, canteens, selectCanteen, shops, shop, shopHref, q, setQ, category, setCategory, period, setPeriod, panelId, items } =
    props;
  return (
    <>
      <header className="flex flex-col gap-3 px-4 pb-2.5 pt-[18px]">
        <div className="flex items-center justify-between">
          <h1 className="m-0 text-2xl font-extrabold tracking-[-0.02em]">Food</h1>
          <CanteenSelect value={canteenId} canteens={canteens} onChange={selectCanteen} />
        </div>
        <SearchField id="food-search" label="Search food" value={q} onChange={setQ} placeholder="Search rice, kottu, drinks…" />
        <FilterChips label="Food type" options={CATEGORIES} value={category} onChange={setCategory} />
      </header>
      <main id="main" className="flex flex-1 flex-col gap-3 px-4 pb-4 pt-1">
        {props.shopsLoading ? (
          <Loading label="Loading shops">
            <Skeleton className="h-[78px]" />
          </Loading>
        ) : shops.length === 0 ? (
          <MessageCard icon="store" dashed title="No shops listed yet" />
        ) : (
          <div aria-label="Shops" className="scrollbar-none -mx-4 flex snap-x gap-2.5 overflow-x-auto px-4">
            {shops.map((s) => (
              <ShopCard key={s.id} shop={s} href={shopHref(s)} selected={s.id === shop?.id} />
            ))}
          </div>
        )}
        <Segmented
          label="Meal period"
          options={PERIOD_OPTIONS}
          value={period}
          onChange={setPeriod}
          panelId={panelId}
          stretch
          className="bg-chip"
        />
        <div id={panelId} role="tabpanel" aria-label={`${PERIOD_LABEL[period]} menu`}>
          {props.menuLoading ? (
            <Loading label="Loading menu">
              <Skeleton className="h-[300px]" />
            </Loading>
          ) : items.length === 0 ? (
            <MenuEmpty {...props} />
          ) : (
            <ul className="m-0 flex list-none flex-col rounded-[18px] border border-line bg-card px-3 py-0.5">
              {items.map((item, i) => (
                <li key={item.id} className={cx("flex items-center gap-3 py-3", i < items.length - 1 && "border-b border-line-soft")}>
                  <ItemArt item={item} className="h-[52px] w-[52px] shrink-0 rounded-[14px]" />
                  <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                    <span className={cx("text-[15px] font-bold", item.is_available ? "text-ink" : "text-faint line-through")}>
                      {item.name}
                    </span>
                    <span className="text-[13px] text-muted">
                      {formatPrice(item.price_lkr)}
                      {item.tags.includes("vegetarian") ? " · Vegetarian" : ""}
                    </span>
                  </span>
                  <AvailabilityChip available={item.is_available} />
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="m-0 text-xs text-muted">
          {props.menuUpdatedAt ? `Menu updated today ${formatClock(props.menuUpdatedAt)} by shop staff` : "Menu not updated yet"}
          {props.isSample ? " · prices are sample values" : ""}
        </p>
      </main>
    </>
  );
}

function FoodWeb(props: FoodViewProps) {
  const { canteenId, canteens, selectCanteen, shops, shop, shopHref, q, setQ, category, setCategory, period, setPeriod, panelId, items } =
    props;
  const canteenName = canteens.find((c) => c.id === canteenId)?.name ?? "this canteen";
  return (
    <main id="main" className="mx-auto flex max-w-[1200px] flex-col gap-5 px-6 pb-10 pt-7">
      <div className="flex flex-wrap items-end justify-between gap-3.5">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-[32px] font-extrabold tracking-[-0.03em]">Food &amp; shops</h1>
          <span className="text-[15px] text-muted">Menus and opening hours, updated by shop staff.</span>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <CanteenSelect value={canteenId} canteens={canteens} onChange={selectCanteen} />
          <SearchField
            id="menu-search"
            label="Search food"
            value={q}
            onChange={setQ}
            placeholder="Search food"
            className="w-[260px] max-w-full"
            inputClassName="rounded-xl"
          />
        </div>
      </div>
      <FilterChips label="Food type" options={CATEGORIES} value={category} onChange={setCategory} wrap />
      <div className="flex flex-wrap items-start gap-5">
        <aside
          aria-label={`Shops in ${canteenName}`}
          className="flex min-w-0 flex-[1_1_300px] flex-col gap-1 rounded-[22px] border border-line bg-card p-2.5"
        >
          {props.shopsLoading ? (
            <Loading label="Loading shops">
              <Skeleton className="h-[68px]" />
              <Skeleton className="h-[68px]" />
            </Loading>
          ) : null}
          {!props.shopsLoading && shops.length === 0 ? <span className="p-3 text-sm text-muted">No shops listed yet</span> : null}
          {shops.map((s) => {
            const selected = s.id === shop?.id;
            return (
              <Link
                key={s.id}
                to={shopHref(s)}
                replace
                aria-current={selected ? "true" : undefined}
                className={cx("flex items-center gap-3 rounded-2xl p-3 text-ink no-underline", selected ? "bg-mint" : "hover:bg-page")}
              >
                <ShopArt shop={s} className="h-11 w-11 shrink-0 rounded-[14px]" />
                <span className="flex flex-1 flex-col gap-0.5">
                  <span className={cx("text-[15px]", selected ? "font-extrabold" : "font-bold")}>{s.name}</span>
                  <ShopStatusDot status={s.status} />
                </span>
              </Link>
            );
          })}
        </aside>
        <section
          aria-labelledby="menu-title"
          className="flex min-w-0 flex-[2.4_1_560px] flex-col gap-4 rounded-[22px] border border-line bg-card p-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-col gap-0.5">
              <h2 id="menu-title" className="m-0 text-xl font-extrabold">
                {shop?.name ?? "Menu"}
              </h2>
              {shop ? (
                <span className="text-[13px] text-muted">
                  {shop.status.state === "temporarily_closed"
                    ? `Temporarily closed${shop.status.reason ? ` — ${shop.status.reason}` : ""} · `
                    : ""}
                  {shop.hours_label}
                  {props.menuUpdatedAt ? ` · menu updated ${formatClock(props.menuUpdatedAt)}` : ""}
                </span>
              ) : null}
            </div>
            <Segmented
              label="Meal period"
              options={PERIOD_OPTIONS}
              value={period}
              onChange={setPeriod}
              panelId={panelId}
              className="bg-line-soft"
            />
          </div>
          <div id={panelId} role="tabpanel" aria-label={`${PERIOD_LABEL[period]} menu`}>
            {props.menuLoading ? (
              <Loading label="Loading menu">
                <Skeleton className="h-[220px]" />
              </Loading>
            ) : items.length === 0 ? (
              <MenuEmpty {...props} />
            ) : (
              <ul className="m-0 flex list-none flex-wrap gap-3.5 p-0">
                {items.map((item) => (
                  <li key={item.id} className="flex flex-[1_1_220px] flex-col overflow-hidden rounded-[18px] border border-line">
                    <ItemArt item={item} className="h-[120px]" fit="contain" />
                    <span className="flex flex-col gap-1.5 px-3.5 pb-3.5 pt-3">
                      <span className={cx("text-[15px] font-bold", item.is_available ? "text-ink" : "text-faint line-through")}>
                        {item.name}
                      </span>
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-[15px] font-extrabold">{formatPrice(item.price_lkr)}</span>
                        <AvailabilityChip available={item.is_available} />
                      </span>
                      {item.tags.includes("vegetarian") ? <span className="text-xs font-bold text-ok">Vegetarian</span> : null}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {props.isSample ? (
            <Footnote>
              Sample data — shop names, items and prices are placeholders until real shops provide them. Pictures are illustrations.
            </Footnote>
          ) : null}
        </section>
      </div>
    </main>
  );
}
