import canteenA from "./art/canteens/canteen-a.webp";
import canteenB from "./art/canteens/canteen-b.webp";
import canteenC from "./art/canteens/canteen-c.webp";
import noAlerts from "./art/empty-states/no-alerts.webp";
import noCanteens from "./art/empty-states/no-canteens.webp";
import noMenu from "./art/empty-states/no-menu.webp";
import noResults from "./art/empty-states/no-results.webp";
import noShops from "./art/empty-states/no-shops.webp";
import offline from "./art/empty-states/offline.webp";
import pageNotFound from "./art/empty-states/page-not-found.webp";
import sensorOffline from "./art/empty-states/sensor-offline.webp";
import butterCake from "./art/food/butter-cake.webp";
import cheeseKottu from "./art/food/cheese-kottu.webp";
import chickenFriedRice from "./art/food/chicken-fried-rice.webp";
import chickenKottu from "./art/food/chicken-kottu.webp";
import chickenNoodles from "./art/food/chicken-noodles.webp";
import chickenRiceCurry from "./art/food/chicken-rice-curry.webp";
import chickenRoll from "./art/food/chicken-roll.webp";
import devilledChickenNoodles from "./art/food/devilled-chicken-noodles.webp";
import dhalPapadam from "./art/food/dhal-papadam.webp";
import eggFriedRice from "./art/food/egg-fried-rice.webp";
import eggKottu from "./art/food/egg-kottu.webp";
import eggSandwich from "./art/food/egg-sandwich.webp";
import fishBun from "./art/food/fish-bun.webp";
import fishRiceCurry from "./art/food/fish-rice-curry.webp";
import icedCoffee from "./art/food/iced-coffee.webp";
import limeJuice from "./art/food/lime-juice.webp";
import mangoSmoothie from "./art/food/mango-smoothie.webp";
import milkRiceLunuMiris from "./art/food/milk-rice-lunu-miris.webp";
import nasiGoreng from "./art/food/nasi-goreng.webp";
import papayaJuice from "./art/food/papaya-juice.webp";
import plainTea from "./art/food/plain-tea.webp";
import samosa from "./art/food/samosa.webp";
import stringHoppersCurry from "./art/food/string-hoppers-curry.webp";
import vegetableFriedRice from "./art/food/vegetable-fried-rice.webp";
import vegetableKottu from "./art/food/vegetable-kottu.webp";
import vegetableNoodles from "./art/food/vegetable-noodles.webp";
import vegetableRiceCurry from "./art/food/vegetable-rice-curry.webp";
import vegetableRoti from "./art/food/vegetable-roti.webp";
import woodAppleJuice from "./art/food/wood-apple-juice.webp";
import shopBakery from "./art/shops/shop-bakery.webp";
import shopDrinks from "./art/shops/shop-drinks.webp";
import shopKottu from "./art/shops/shop-kottu.webp";
import shopNoodles from "./art/shops/shop-noodles.webp";
import shopRice from "./art/shops/shop-rice.webp";
import shopShortEats from "./art/shops/shop-short-eats.webp";
import shopTea from "./art/shops/shop-tea.webp";
import welcomeHero from "./art/welcome/welcome-hero.webp";
import type { ShopArtKind } from "./food";

export const PHOTO_ART = true;

export type EmptyArt =
  "no-alerts" | "no-canteens" | "no-menu" | "no-results" | "no-shops" | "offline" | "page-not-found" | "sensor-offline";

const FOOD: Record<string, string> = {
  "butter cake slice": butterCake,
  "cheese kottu": cheeseKottu,
  "chicken fried rice": chickenFriedRice,
  "chicken kottu": chickenKottu,
  "chicken noodles": chickenNoodles,
  "chicken rice & curry": chickenRiceCurry,
  "chicken roll": chickenRoll,
  "devilled chicken noodles": devilledChickenNoodles,
  "dhal & papadam (add-on)": dhalPapadam,
  "egg fried rice": eggFriedRice,
  "egg kottu": eggKottu,
  "egg sandwich": eggSandwich,
  "fish bun": fishBun,
  "fish rice & curry": fishRiceCurry,
  "iced coffee": icedCoffee,
  "lime juice": limeJuice,
  "mango smoothie": mangoSmoothie,
  "milk rice & lunu miris": milkRiceLunuMiris,
  "nasi goreng": nasiGoreng,
  "papaya juice": papayaJuice,
  "plain tea": plainTea,
  samosa,
  "string hoppers & curry": stringHoppersCurry,
  "vegetable fried rice": vegetableFriedRice,
  "vegetable kottu": vegetableKottu,
  "vegetable noodles": vegetableNoodles,
  "vegetable rice & curry": vegetableRiceCurry,
  "vegetable roti": vegetableRoti,
  "wood apple juice": woodAppleJuice,
};

const SHOP_BY_ID: Record<string, string> = {
  "s-rice": shopRice,
  "s-friedrice": shopRice,
  "s-kottu": shopKottu,
  "s-shorteats": shopShortEats,
  "s-tea": shopTea,
  "s-noodle": shopNoodles,
  "s-bakery": shopBakery,
  "s-smoothie": shopDrinks,
  "s-juice": shopDrinks,
};

const SHOP_BY_KIND: Record<ShopArtKind, string> = {
  rice: shopRice,
  kottu: shopKottu,
  short_eats: shopShortEats,
  tea: shopTea,
  noodles: shopNoodles,
  bakery: shopBakery,
  drinks: shopDrinks,
};

const CANTEENS: Record<string, string> = { a: canteenA, b: canteenB, c: canteenC };

const EMPTY: Record<EmptyArt, string> = {
  "no-alerts": noAlerts,
  "no-canteens": noCanteens,
  "no-menu": noMenu,
  "no-results": noResults,
  "no-shops": noShops,
  offline,
  "page-not-found": pageNotFound,
  "sensor-offline": sensorOffline,
};

function enabled(src: string | undefined): string | undefined {
  return PHOTO_ART ? src : undefined;
}

export function foodPhotoFor(name: string): string | undefined {
  return enabled(FOOD[name.trim().toLowerCase()]);
}

export function shopPhotoFor(id: string, kind: ShopArtKind): string | undefined {
  return enabled(SHOP_BY_ID[id] ?? SHOP_BY_KIND[kind]);
}

export function canteenPhotoFor(id: string): string | undefined {
  return enabled(CANTEENS[id]);
}

export function welcomePhoto(): string | undefined {
  return enabled(welcomeHero);
}

export function emptyArtFor(art: EmptyArt | undefined): string | undefined {
  return art ? enabled(EMPTY[art]) : undefined;
}
