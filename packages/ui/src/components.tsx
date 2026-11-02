import type { CrowdLevel, Freshness } from "@dinemate/api-client";
import type { ReactNode } from "react";
import { cx } from "./cx";
import { Icon } from "./icons";
import { levelFor } from "./levels";

export const APP_NAME = "DineMate";

type PillSize = "sm" | "md" | "lg";

const PILL_SIZES: Record<PillSize, { box: string; icon: number }> = {
  sm: { box: "gap-1 px-2 py-[3px] text-[11px]", icon: 12 },
  md: { box: "gap-[5px] px-2.5 py-[5px] text-xs", icon: 13 },
  lg: { box: "gap-1.5 px-3 py-1.5 text-[13px]", icon: 14 },
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
      <Icon name={style.icon} size={dims.icon} strokeWidth={2.4} />
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
      ) : (
        <CanteenScene wall={wall} />
      )}
      {label ? (
        <span
          aria-hidden="true"
          className="absolute left-2.5 top-2.5 flex h-[30px] min-w-[30px] items-center justify-center rounded-[9px] bg-brand-dark px-2 text-[15px] font-extrabold text-white"
        >
          {label}
        </span>
      ) : null}
    </div>
  );
}

function CanteenScene({ wall }: { wall: string }) {
  return (
    <svg
      aria-hidden="true"
      width="100%"
      height="100%"
      viewBox="0 0 320 200"
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 block"
    >
      <rect x="0" y="0" width="320" height="200" fill={wall} />
      <rect x="0" y="0" width="320" height="14" fill="#FFFFFF" opacity="0.45" />
      {[18, 118, 218].map((x, i) => (
        <g key={x}>
          <rect x={x} y="28" width="84" height="92" rx="4" fill="#EAF7FB" stroke="#FFFFFF" strokeWidth="5" />
          <circle cx={x + 20} cy="102" r="14" fill={i === 1 ? "#7CC48F" : "#9ED4AE"} />
          <circle cx={x + 52} cy="98" r="18" fill={i === 1 ? "#9ED4AE" : "#7CC48F"} />
          <circle cx={x + 74} cy="106" r="10" fill={i === 1 ? "#7CC48F" : "#9ED4AE"} />
          <line x1={x + 42} y1="28" x2={x + 42} y2="120" stroke="#FFFFFF" strokeWidth="4" />
        </g>
      ))}
      <rect x="0" y="120" width="320" height="6" fill="#FFFFFF" opacity="0.7" />
      {[70, 160, 250].map((x) => (
        <g key={x}>
          <line x1={x} y1="0" x2={x} y2="40" stroke="#56645B" strokeWidth="1.5" />
          <path d={`M${x - 12} 52 Q${x} 34 ${x + 12} 52 Z`} fill="#F2C14E" />
        </g>
      ))}
      <rect x="0" y="150" width="320" height="50" fill="#EADFCB" />
      <line x1="0" y1="150" x2="320" y2="150" stroke="#D8C8AC" strokeWidth="2" />
      {[
        [34, 34, 52],
        [160, 142, 144],
        [174, 174, 192],
        [300, 282, 284],
      ].map(([back, seat, leg]) => (
        <g key={back} fill="#2F6B4A">
          <rect x={back} y="122" width="6" height="48" rx="2" />
          <rect x={seat} y="148" width="24" height="5" rx="2" />
          <rect x={leg} y="153" width="4" height="20" />
        </g>
      ))}
      {[50, 190].map((x) => (
        <g key={x}>
          <rect x={x} y="138" width="100" height="7" rx="2" fill="#B07A45" />
          <rect x={x + 8} y="145" width="5" height="30" fill="#8C5D33" />
          <rect x={x + 87} y="145" width="5" height="30" fill="#8C5D33" />
        </g>
      ))}
      <ellipse cx="10" cy="158" rx="6" ry="12" fill="#4E9F68" transform="rotate(-20 10 158)" />
      <ellipse cx="19" cy="156" rx="6" ry="13" fill="#3E8A57" transform="rotate(18 19 156)" />
      <path d="M3 168h22l-3 22H6z" fill="#C96F4A" />
    </svg>
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

export function SampleBadge({ children = "SAMPLE DATA", className }: { children?: ReactNode; className?: string }) {
  return (
    <span className={cx("shrink-0 rounded-md bg-chip px-2 py-1 text-[11px] font-extrabold text-neutral-ink", className)}>{children}</span>
  );
}

export function BrandMark({ size = 38, className }: { size?: number; className?: string }) {
  return (
    <span
      className={cx("flex shrink-0 items-center justify-center rounded-xl bg-mint text-brand", className)}
      style={{ width: size, height: size }}
    >
      <Icon name="leaf" size={Math.round(size * 0.58)} />
    </span>
  );
}

export function LiveLine({ text, freshness = "live" }: { text: string; freshness?: Freshness }) {
  const live = freshness === "live";
  return (
    <span className={cx("inline-flex items-center gap-1.5 text-[13px] font-bold", live ? "text-ok" : "text-neutral-ink")}>
      <span className={cx("h-2 w-2 rounded-full", live ? "bg-ok-mark" : "bg-dash")} />
      {text}
    </span>
  );
}
