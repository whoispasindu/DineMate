import type { ReactNode } from "react";
import { cx } from "./cx";

export type FoodArtKind =
  "rice_curry" | "fried_rice" | "milk_rice" | "string_hoppers" | "dhal" | "kottu" | "short_eats" | "bakery" | "noodles" | "tea" | "drink";

export type ShopArtKind = "rice" | "kottu" | "short_eats" | "tea" | "noodles" | "bakery" | "drinks";

const BACKDROP: Record<FoodArtKind, string> = {
  rice_curry: "#FCEFD9",
  fried_rice: "#FBEBCB",
  milk_rice: "#F3F7F2",
  string_hoppers: "#EEF4EA",
  dhal: "#FFF4D6",
  kottu: "#FDE3D3",
  short_eats: "#F7E7D3",
  bakery: "#FBEFE4",
  noodles: "#E3F1E8",
  tea: "#EFE6DA",
  drink: "#E7EEF9",
};

const DRINK_COLORS: [RegExp, string, string][] = [
  [/mango/i, "#F5B83D", "#E79A1E"],
  [/papaya/i, "#F28A4B", "#DD6B2C"],
  [/lime|lemon/i, "#C9DF6A", "#A9C447"],
  [/wood ?apple/i, "#A9743F", "#8A5A2B"],
  [/coffee|milo/i, "#9B6A43", "#7A4E2D"],
];

const SHOP_ART: Record<ShopArtKind, FoodArtKind> = {
  rice: "rice_curry",
  kottu: "kottu",
  short_eats: "short_eats",
  tea: "tea",
  noodles: "noodles",
  bakery: "bakery",
  drinks: "drink",
};

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

export function shopArtFor(kind: ShopArtKind): FoodArtKind {
  return SHOP_ART[kind];
}

function Plate({ children }: { children: ReactNode }) {
  return (
    <>
      <ellipse cx="80" cy="74" rx="62" ry="30" fill="#000000" opacity="0.06" />
      <ellipse cx="80" cy="70" rx="60" ry="29" fill="#FFFFFF" />
      <ellipse cx="80" cy="70" rx="47" ry="21" fill="none" stroke="#E6EAE4" strokeWidth="2" />
      {children}
    </>
  );
}

function Dots({ points, fill, r = 2.2 }: { points: [number, number][]; fill: string; r?: number }) {
  return (
    <>
      {points.map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill={fill} />
      ))}
    </>
  );
}

function RiceCurry() {
  return (
    <Plate>
      <path d="M44 72c0-14 13-22 28-22s26 8 26 20c0 6-12 9-27 9s-27-2-27-7z" fill="#FBF6E9" />
      <path d="M52 62c6-4 14-5 20-4" stroke="#EFE6CF" strokeWidth="2" fill="none" strokeLinecap="round" />
      <ellipse cx="106" cy="62" rx="13" ry="7" fill="#E9A23B" />
      <ellipse cx="106" cy="61" rx="10" ry="4.5" fill="#F4BE57" />
      <ellipse cx="104" cy="80" rx="12" ry="6" fill="#B8432F" />
      <ellipse cx="104" cy="79" rx="9" ry="3.8" fill="#D2583E" />
      <ellipse cx="62" cy="84" rx="13" ry="5.5" fill="#6FA654" />
      <Dots
        points={[
          [57, 83],
          [64, 85],
          [68, 82],
        ]}
        fill="#4C8238"
        r={1.6}
      />
    </Plate>
  );
}

function FriedRice() {
  return (
    <Plate>
      <path d="M38 74c0-15 18-25 42-25s42 10 42 24c0 7-19 11-42 11s-42-3-42-10z" fill="#E7C46A" />
      <path d="M50 62c10-6 26-8 40-6" stroke="#F0D488" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <Dots
        points={[
          [56, 66],
          [72, 60],
          [90, 64],
          [104, 70],
          [66, 74],
          [84, 76],
          [98, 60],
        ]}
        fill="#6BAF5B"
      />
      <Dots
        points={[
          [62, 60],
          [80, 68],
          [94, 74],
          [74, 78],
          [108, 66],
          [50, 72],
        ]}
        fill="#E58A3A"
      />
      <path d="M86 56l9-3 4 6-8 4z" fill="#FFF6D0" />
      <path d="M58 76l8-2 3 5-8 3z" fill="#FFF6D0" />
    </Plate>
  );
}

const MILK_RICE: [number, number][] = [
  [56, 62],
  [80, 58],
  [68, 76],
  [92, 72],
];

const HOPPERS: [number, number][] = [
  [58, 64],
  [84, 60],
  [70, 80],
  [98, 76],
];

function MilkRice() {
  return (
    <Plate>
      {MILK_RICE.map(([x, y]) => (
        <g key={`${x}-${y}`}>
          <path d={`M${x} ${y - 10}l13 9-13 9-13-9z`} fill="#FFFDF5" stroke="#EDE6D2" strokeWidth="1.5" />
          <path d={`M${x - 13} ${y - 1}l13 9v4l-13-9z`} fill="#EDE6D2" />
          <path d={`M${x + 13} ${y - 1}l-13 9v4l13-9z`} fill="#E3DAC2" />
        </g>
      ))}
      <ellipse cx="114" cy="66" rx="11" ry="6" fill="#C7432E" />
      <Dots
        points={[
          [110, 64],
          [116, 67],
          [119, 64],
        ]}
        fill="#E9A23B"
        r={1.5}
      />
    </Plate>
  );
}

function StringHoppers() {
  return (
    <Plate>
      {HOPPERS.map(([x, y]) => (
        <g key={`${x}-${y}`}>
          <ellipse cx={x} cy={y} rx="14" ry="7.5" fill="#F7F1E1" />
          <ellipse cx={x} cy={y} rx="11" ry="5.5" fill="none" stroke="#E4D8BA" strokeWidth="1.4" strokeDasharray="2 1.5" />
          <ellipse cx={x} cy={y} rx="6" ry="3" fill="none" stroke="#E4D8BA" strokeWidth="1.4" strokeDasharray="2 1.5" />
        </g>
      ))}
      <ellipse cx="118" cy="66" rx="10" ry="5.5" fill="#E9A23B" />
    </Plate>
  );
}

function Dhal() {
  return (
    <Plate>
      <circle cx="98" cy="64" r="22" fill="#F3D79A" />
      <circle cx="98" cy="64" r="22" fill="none" stroke="#E5C177" strokeWidth="2" />
      <Dots
        points={[
          [90, 58],
          [104, 56],
          [96, 70],
          [108, 68],
          [86, 68],
        ]}
        fill="#E8C57F"
        r={3}
      />
      <path d="M44 74a22 11 0 0 1 44 0z" fill="#D8892F" />
      <ellipse cx="66" cy="72" rx="22" ry="8" fill="#F2B640" />
      <ellipse cx="66" cy="71" rx="18" ry="5.5" fill="#F7C95B" />
      <Dots
        points={[
          [60, 70],
          [70, 72],
          [66, 69],
        ]}
        fill="#C46A22"
        r={1.4}
      />
    </Plate>
  );
}

function Kottu() {
  const strips: [number, number, number][] = [
    [52, 66, -18],
    [64, 60, 12],
    [78, 64, -8],
    [92, 60, 20],
    [104, 68, -14],
    [58, 76, 10],
    [74, 74, -20],
    [88, 76, 8],
    [100, 78, -6],
    [70, 66, 28],
  ];
  return (
    <Plate>
      <path d="M40 74c0-14 18-23 40-23s40 9 40 22c0 7-18 10-40 10s-40-3-40-9z" fill="#E7C795" />
      {strips.map(([x, y, a]) => (
        <rect
          key={`${x}-${y}`}
          x={x - 9}
          y={y - 3}
          width="18"
          height="6"
          rx="3"
          fill="#F3DDB4"
          stroke="#D9B47C"
          strokeWidth="1"
          transform={`rotate(${a} ${x} ${y})`}
        />
      ))}
      <Dots
        points={[
          [60, 70],
          [82, 68],
          [96, 72],
          [72, 80],
          [88, 62],
        ]}
        fill="#5FA34F"
      />
      <Dots
        points={[
          [68, 62],
          [90, 80],
          [104, 62],
          [56, 80],
        ]}
        fill="#E2683C"
      />
    </Plate>
  );
}

function ShortEats() {
  return (
    <>
      <ellipse cx="80" cy="84" rx="60" ry="14" fill="#000000" opacity="0.06" />
      <path d="M22 80l116-6 4 12-116 6z" fill="#FFFFFF" />
      <path d="M22 80l116-6" stroke="#E6EAE4" strokeWidth="1.5" />
      <path d="M30 78c0-16 12-26 24-26s24 10 24 26z" fill="#C9894A" />
      <path d="M38 64c4-6 10-8 16-8" stroke="#DDA567" strokeWidth="3" fill="none" strokeLinecap="round" />
      <Dots
        points={[
          [46, 62],
          [54, 58],
          [62, 63],
        ]}
        fill="#E9D9B8"
        r={1.3}
      />
      <rect x="76" y="58" width="36" height="18" rx="9" fill="#D79E58" transform="rotate(-8 94 67)" />
      <ellipse cx="111" cy="64" rx="5" ry="8.5" fill="#E9C48C" transform="rotate(-8 111 64)" />
      <Dots
        points={[
          [84, 66],
          [92, 62],
          [100, 66],
        ]}
        fill="#B9803F"
        r={1.2}
      />
      <path d="M108 82l14-24 14 24z" fill="#E1AE58" stroke="#C99441" strokeWidth="1.5" strokeLinejoin="round" />
    </>
  );
}

function Bakery() {
  return (
    <>
      <ellipse cx="80" cy="86" rx="58" ry="12" fill="#000000" opacity="0.06" />
      <path d="M30 82l26-34 26 34z" fill="#F4D9A6" />
      <path d="M30 82l26-34 4 6-24 30z" fill="#E9C688" />
      <path d="M33 78l23-30 23 30" fill="none" stroke="#FFFFFF" strokeWidth="4" strokeLinejoin="round" />
      <rect x="32" y="74" width="48" height="10" rx="2" fill="#E7B970" />
      <path d="M92 56h40l-4 26H96z" fill="#F7E7C6" />
      <path d="M92 56h40v6H92z" fill="#C98B4A" />
      <path d="M96 66h32" stroke="#E3C690" strokeWidth="2" />
      <path d="M98 72h28" stroke="#9BC57E" strokeWidth="3" strokeLinecap="round" />
      <path d="M98 77h28" stroke="#F5D04E" strokeWidth="2.5" strokeLinecap="round" />
    </>
  );
}

function Noodles() {
  return (
    <>
      <ellipse cx="80" cy="88" rx="50" ry="10" fill="#000000" opacity="0.06" />
      <path d="M32 58h96c0 20-20 32-48 32S32 78 32 58z" fill="#2F6B4A" />
      <ellipse cx="80" cy="58" rx="48" ry="14" fill="#245A3E" />
      <ellipse cx="80" cy="57" rx="44" ry="11" fill="#F0CF73" />
      {[0, 1, 2, 3].map((i) => (
        <path
          key={i}
          d={`M${44 + i * 4} ${53 + i * 2.5}c8-6 16 6 24 0s16 6 24 0 16 6 24 0`}
          stroke="#E2B451"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
      ))}
      <Dots
        points={[
          [58, 54],
          [96, 52],
          [84, 62],
        ]}
        fill="#5FA34F"
        r={2.6}
      />
      <Dots
        points={[
          [70, 50],
          [104, 60],
        ]}
        fill="#E2683C"
        r={2.6}
      />
      <path d="M108 30l-26 26M118 34l-30 24" stroke="#B07A45" strokeWidth="3" strokeLinecap="round" />
    </>
  );
}

function Tea() {
  return (
    <>
      <ellipse cx="80" cy="88" rx="44" ry="9" fill="#000000" opacity="0.06" />
      <ellipse cx="80" cy="84" rx="40" ry="9" fill="#FFFFFF" />
      <path d="M54 50h52l-6 32H60z" fill="#FFFFFF" stroke="#E6EAE4" strokeWidth="2" />
      <ellipse cx="80" cy="50" rx="26" ry="6" fill="#C68A4E" />
      <path d="M106 56c12 0 12 18 0 18" stroke="#E6EAE4" strokeWidth="4" fill="none" />
      <path
        d="M70 40c-4-6 4-10 0-16M82 40c-4-6 4-10 0-16M94 40c-4-6 4-10 0-16"
        stroke="#C9B9A6"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
    </>
  );
}

function Drink({ name }: { name: string }) {
  const [, liquid, shade] = DRINK_COLORS.find(([pattern]) => pattern.test(name)) ?? [/./, "#F2994A", "#DB7B2E"];
  return (
    <>
      <ellipse cx="80" cy="96" rx="26" ry="5" fill="#000000" opacity="0.06" />
      <path d="M62 30h36l-5 64H67z" fill="#FFFFFF" opacity="0.85" stroke="#DCE3EC" strokeWidth="2" />
      <path d="M64 46h32l-4 46H68z" fill={liquid} />
      <path d="M64 46h32l-1 8H65z" fill={shade} opacity="0.5" />
      <rect x="71" y="56" width="8" height="8" rx="2" fill="#FFFFFF" opacity="0.55" transform="rotate(12 75 60)" />
      <rect x="82" y="66" width="7" height="7" rx="2" fill="#FFFFFF" opacity="0.45" transform="rotate(-10 85 69)" />
      <path d="M88 20l-6 52" stroke="#E2683C" strokeWidth="4" strokeLinecap="round" />
      <circle cx="104" cy="40" r="8" fill="#9BC57E" />
      <path d="M104 32v16M96 40h16" stroke="#7DAA5F" strokeWidth="1.5" />
    </>
  );
}

const ART: Record<Exclude<FoodArtKind, "drink">, () => ReactNode> = {
  rice_curry: RiceCurry,
  fried_rice: FriedRice,
  milk_rice: MilkRice,
  string_hoppers: StringHoppers,
  dhal: Dhal,
  kottu: Kottu,
  short_eats: ShortEats,
  bakery: Bakery,
  noodles: Noodles,
  tea: Tea,
};

interface FoodArtProps {
  kind: FoodArtKind;
  name?: string;
  className?: string;
  muted?: boolean;
  fit?: "cover" | "contain";
  photo?: string;
}

export function FoodArt({ kind, name = "", className, muted, fit = "cover", photo }: FoodArtProps) {
  if (photo) {
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
  const Art = kind === "drink" ? null : ART[kind];
  return (
    <span className={cx("block overflow-hidden", muted && "opacity-50 grayscale", className)} style={{ background: BACKDROP[kind] }}>
      <svg
        aria-hidden="true"
        viewBox="0 0 160 120"
        width="100%"
        height="100%"
        preserveAspectRatio={fit === "cover" ? "xMidYMid slice" : "xMidYMid meet"}
        className="block"
      >
        <rect width="160" height="120" fill={BACKDROP[kind]} />
        <circle cx="140" cy="18" r="30" fill="#FFFFFF" opacity="0.35" />
        <circle cx="16" cy="108" r="22" fill="#FFFFFF" opacity="0.3" />
        {Art ? <Art /> : <Drink name={name} />}
      </svg>
    </span>
  );
}
