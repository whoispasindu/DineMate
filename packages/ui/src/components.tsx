import type { CrowdLevel, Freshness } from "@dinemate/api-client";
import type { ReactNode } from "react";
import { cx } from "./cx";
import { Icon } from "./icons";
import { levelFor } from "./levels";
import tableScene from "./art/scene/table.svg";

export const APP_NAME = "DineMate";

type PillSize = "sm" | "md" | "lg";

const PILL_SIZES: Record<PillSize, { box: string; icon: number }> = {
  sm: { box: "h-6 px-2.5 text-xs", icon: 12 },
  md: { box: "h-7 px-3 text-xs", icon: 13 },
  lg: { box: "h-8 px-3.5 text-[13px]", icon: 14 },
};

interface StatusPillProps {
  level: CrowdLevel;
  freshness?: Freshness;
  size?: PillSize;
  onWhite?: boolean;
  label?: string;
  className?: string;
}

export function StatusPill({ level, freshness = "live", size = "md", onWhite, label, className }: StatusPillProps) {
  const style = levelFor(level, freshness);
  const dims = PILL_SIZES[size];
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full font-bold",
        dims.box,
        style.pill,
        onWhite && "bg-card",
        className,
      )}
    >
      {label ?? style.label}
    </span>
  );
}

interface RingProps {
  percent: number | null;
  level: CrowdLevel;
  freshness?: Freshness;
  size: number;
  thickness: number;
  className?: string;
  textClassName?: string;
}

export function Ring({ percent, level, freshness = "live", size, thickness, className, textClassName }: RingProps) {
  if (percent === null || freshness === "unavailable") {
    return (
      <div
        role="img"
        aria-label="No live data"
        className={cx("flex shrink-0 items-center justify-center rounded-full border-dashed border-dash-soft text-neutral-ink", className)}
        style={{ width: size, height: size, borderWidth: thickness }}
      >
        <Icon name="question" size={Math.round(size * 0.28)} strokeWidth={2.2} />
      </div>
    );
  }
  const mark = levelFor(level, freshness).mark;
  const inner = size - thickness * 2;
  return (
    <div
      role="img"
      aria-label={`About ${percent}% of seats in use`}
      className={cx("flex shrink-0 items-center justify-center rounded-full", freshness === "stale" && "opacity-60", className)}
      style={{ width: size, height: size, background: `conic-gradient(${mark} 0 ${percent}%, var(--color-track) ${percent}% 100%)` }}
    >
      <div
        aria-hidden="true"
        className={cx("flex items-center justify-center rounded-full bg-card font-extrabold", textClassName)}
        style={{ width: inner, height: inner }}
      >
        {percent}%
      </div>
    </div>
  );
}

interface HalfGaugeProps {
  percent: number | null;
  level: CrowdLevel;
  freshness?: Freshness;
  caption: string;
}

export function HalfGauge({ percent, level, freshness = "live", caption }: HalfGaugeProps) {
  const mark = levelFor(level, freshness).mark;
  const degrees = percent === null ? 0 : Math.round(percent * 1.8);
  return (
    <div
      role="img"
      aria-label={percent === null ? "No live data" : `About ${percent}% of seats in use`}
      className={cx("relative h-[110px] w-[220px] shrink-0 overflow-hidden", freshness === "stale" && "opacity-60")}
    >
      <div
        className="absolute left-0 top-0 h-[220px] w-[220px] rounded-full"
        style={{
          background: `conic-gradient(from -90deg, ${mark} 0deg ${degrees}deg, var(--color-track) ${degrees}deg 180deg, transparent 180deg 360deg)`,
        }}
      />
      <div className="absolute left-6 top-6 h-[172px] w-[172px] rounded-full bg-card" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0.5 flex flex-col items-center">
        <span className="text-[34px] font-extrabold leading-none tracking-[-0.02em]">{percent === null ? "—" : `${percent}%`}</span>
        <span className="text-xs text-muted">{caption}</span>
      </div>
    </div>
  );
}

interface CanteenArtProps {
  wall: string;
  label?: string;
  className?: string;
  photo?: string;
}

export function CanteenArt({ wall, label, className, photo }: CanteenArtProps) {
  return (
    <div className={cx("relative h-full min-h-[60px] w-full overflow-hidden", className)} style={{ background: wall }}>
      {photo ? (
        <img src={photo} alt="" loading="lazy" decoding="async" className="absolute inset-0 block h-full w-full object-cover" />
      ) : null}
      {label ? (
        <span
          aria-hidden="true"
          className="absolute left-2.5 top-2.5 flex h-[26px] min-w-[26px] items-center justify-center rounded-[9px] bg-brand px-1.5 font-display text-[13px] font-extrabold text-sand"
        >
          {label}
        </span>
      ) : null}
    </div>
  );
}

interface HazardFrameProps {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
  tight?: boolean;
}

export function HazardFrame({ children, className, innerClassName, tight }: HazardFrameProps) {
  return (
    <section role="alert" className={cx("rounded-[22px] p-[5px]", tight ? "hazard-stripes-tight" : "hazard-stripes", className)}>
      <div className={cx("rounded-[18px] bg-danger-surface", innerClassName)}>{children}</div>
    </section>
  );
}

export function SimulationLabel({ children = "SIMULATION — NOT A REAL EMERGENCY" }: { children?: ReactNode }) {
  return (
    <span className="self-start rounded-[5px] bg-hazard-black px-2 py-[3px] text-[11px] font-extrabold tracking-[0.05em] text-hazard-yellow">
      {children}
    </span>
  );
}

export function SampleBadge({ children = "Sample data", className }: { children?: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex h-7 shrink-0 items-center rounded-full bg-chip px-3 text-xs font-bold text-ink-2", className)}>
      {children}
    </span>
  );
}

export function BrandMark({ size = 38, tone = "forest", className }: { size?: number; tone?: "forest" | "sand"; className?: string }) {
  const bg = tone === "forest" ? "var(--color-brand)" : "var(--color-sand)";
  const fg = tone === "forest" ? "var(--color-sand)" : "var(--color-brand)";
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true" className={cx("shrink-0", className)}>
      <rect width="34" height="34" rx="10" fill={bg} />
      <path d="M11 8.5v10.5h12" fill="none" stroke={fg} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11 19v6.5M21.5 19v6.5" stroke={fg} strokeWidth="2.6" strokeLinecap="round" />
      <path d="M15 14.5h9" stroke="var(--color-purple)" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

interface SeatStripProps {
  total: number;
  taken: number;
  held?: number;
  hidden?: number;
  dark?: boolean;
  height?: number;
  className?: string;
  stale?: boolean;
}

export function SeatStrip({ total, taken, held = 0, hidden = 0, dark, height = 8, className, stale }: SeatStripProps) {
  const free = Math.max(total - taken - held - hidden, 0);
  const parts: { n: number; className: string }[] = [
    { n: taken, className: dark ? "bg-sand" : "bg-brand" },
    { n: held, className: "bg-held" },
    { n: hidden, className: dark ? "bg-sand/35" : "bg-hidden" },
    { n: free, className: dark ? "bg-sand/15" : "bg-track" },
  ];
  return (
    <div
      aria-hidden="true"
      className={cx("flex w-full gap-0.5 overflow-hidden", stale && "opacity-50", className)}
      style={{ height, borderRadius: height }}
    >
      {parts
        .filter((p) => p.n > 0)
        .map((p, i) => (
          <div key={i} className={p.className} style={{ flex: p.n }} />
        ))}
    </div>
  );
}

export function EmptyStrip({ height = 8, className }: { height?: number; className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cx("w-full border-[1.5px] border-dashed border-dash-soft", className)}
      style={{ height, borderRadius: height }}
    />
  );
}

export function TableScene({ width = 120, className }: { width?: number; className?: string }) {
  return <img src={tableScene} alt="" width={width} height={Math.round(width * 1.09)} className={cx("block shrink-0", className)} />;
}

export function LiveLine({ text, freshness = "live" }: { text: string; freshness?: Freshness }) {
  const live = freshness === "live";
  return (
    <span
      className={cx(
        "inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-xs font-bold",
        live ? "bg-purple-bg text-purple-ink" : "bg-chip text-neutral-ink",
      )}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", live ? "bg-purple" : "bg-dash")} />
      {text}
    </span>
  );
}
