import { cx } from "./cx";

export type FoodArtKind =
  "rice_curry" | "fried_rice" | "milk_rice" | "string_hoppers" | "dhal" | "kottu" | "short_eats" | "bakery" | "noodles" | "tea" | "drink";

export type ShopArtKind = "rice" | "kottu" | "short_eats" | "tea" | "noodles" | "bakery" | "drinks";

export function foodArtFor(name: string, tags: readonly string[] = []): FoodArtKind {
  if (/string hopper/i.test(name)) return "string_hoppers";
  if (/milk rice|kiribath/i.test(name)) return "milk_rice";
  if (/fried rice|nasi goreng|biriyani/i.test(name)) return "fried_rice";
  if (/kottu/i.test(name) || tags.includes("kottu")) return "kottu";
  if (/noodle/i.test(name)) return "noodles";
  if (/dhal|papadam/i.test(name)) return "dhal";
  if (/\btea\b|plain tea/i.test(name)) return "tea";
  if (/juice|smoothie|coffee|milo|faluda/i.test(name) || tags.includes("drinks")) return "drink";
  if (/cake|sandwich|bread|pastry/i.test(name)) return "bakery";
  if (/bun|roll|samosa|roti|patty|cutlet|vadai/i.test(name) || tags.includes("short_eats")) return "short_eats";
  return "rice_curry";
}

interface FoodArtProps {
  photo: string;
  className?: string;
  muted?: boolean;
  fit?: "cover" | "contain";
}

export function FoodArt({ photo, className, muted, fit = "cover" }: FoodArtProps) {
  return (
    <span className={cx("block overflow-hidden bg-[#E6D6C3]", muted && "opacity-50 grayscale", className)}>
      <img
        src={photo}
        alt=""
        loading="lazy"
        decoding="async"
        className={cx("block h-full w-full", fit === "cover" ? "object-cover" : "object-contain")}
      />
    </span>
  );
}
