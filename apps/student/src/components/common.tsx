import type { CanteenSummary, SafetyEvent, ShopStatus } from "@dinemate/api-client";
import {
  cx,
  emptyArtFor,
  formatClock,
  formatLocalHM,
  HazardFrame,
  Icon,
  SimulationLabel,
  type EmptyArt,
  type IconName,
} from "@dinemate/ui";
import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { Link } from "react-router";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("rounded-[18px] bg-line-soft motion-safe:animate-pulse", className)} />;
}

export function Loading({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-3.5">
      {children}
    </div>
  );
}

interface MessageCardProps {
  icon: IconName;
  title: string;
  body?: string;
  dashed?: boolean;
  className?: string;
  art?: EmptyArt;
}

export function MessageCard({ icon, title, body, dashed, className, art }: MessageCardProps) {
  const picture = emptyArtFor(art);
  return (
    <div
      className={cx(
        "flex gap-3 rounded-[18px] bg-card p-4",
        picture ? "items-center" : "items-start",
        dashed ? "border-[1.5px] border-dashed border-dash bg-surface-soft" : "border border-line",
        className,
      )}
    >
      {picture ? (
        <img src={picture} alt="" loading="lazy" decoding="async" className="h-16 w-16 shrink-0 object-contain" />
      ) : (
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-neutral text-neutral-ink">
          <Icon name={icon} size={20} strokeWidth={2.2} />
        </span>
      )}
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-bold">{title}</span>
        {body ? <span className="text-[13px] leading-snug text-muted">{body}</span> : null}
      </span>
    </div>
  );
}

export function OfflineCard() {
  return (
    <MessageCard
      icon="wifiOff"
      art="offline"
      dashed
      title="You're offline"
      body="Showing nothing until we reconnect — seat numbers are never shown from memory."
    />
  );
}

export function Footnote({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cx("m-0 flex items-start gap-1.5 text-xs leading-normal text-muted", className)}>
      <Icon name="info" size={14} className="mt-px shrink-0" />
      <span>{children}</span>
    </p>
  );
}

interface SafetyBannerProps {
  event: SafetyEvent;
  layout: "mobile" | "web";
}

export function SafetyBanner({ event, layout }: SafetyBannerProps) {
  const time = formatClock(event.occurred_at);
  if (layout === "web") {
    return (
      <HazardFrame innerClassName="flex flex-wrap items-center gap-4 px-5 py-[18px]">
        <span className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-2xl bg-crowd-bg text-crowd">
          <Icon name="flame" size={26} />
        </span>
        <div className="flex flex-[1_1_300px] flex-col gap-1.5">
          {event.is_simulation ? <SimulationLabel /> : null}
          <span className="text-lg font-extrabold text-danger-ink">
            {event.title}
            {event.canteen_name ? ` · ${event.canteen_name}` : ""}
          </span>
          <span className="text-sm text-danger-body">{event.instructions}</span>
        </div>
        <span className="whitespace-nowrap text-[13px] text-danger-meta">{time}</span>
      </HazardFrame>
    );
  }
  return (
    <HazardFrame tight className="rounded-[20px]" innerClassName="flex flex-col gap-2 rounded-2xl p-3.5">
      {event.is_simulation ? <SimulationLabel /> : null}
      <div className="flex items-center gap-2.5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-crowd-bg text-crowd">
          <Icon name="flame" size={20} />
        </span>
        <div className="flex flex-col">
          <span className="text-[15px] font-extrabold text-danger-ink">{event.title}</span>
          <span className="text-xs text-danger-meta">
            {event.canteen_name ? `${event.canteen_name} · ` : ""}
            {time}
          </span>
        </div>
      </div>
      <span className="text-[13px] leading-[1.45] text-danger-body">{event.instructions}</span>
    </HazardFrame>
  );
}

export function SafetyCompact({ event }: { event: SafetyEvent }) {
  return (
    <HazardFrame tight className="rounded-2xl p-[3px]" innerClassName="rounded-[13px]">
      <Link to="/alerts" className="flex min-h-11 items-center gap-2.5 px-3 text-danger-ink no-underline">
        <Icon name="flame" size={18} className="shrink-0" />
        <span className="min-w-0 flex-1 truncate text-sm font-bold">{event.title}</span>
        <span className="shrink-0 rounded bg-hazard-black px-1.5 py-0.5 text-[11px] font-bold text-hazard-yellow">Simulation</span>
        <Icon name="chevronRight" size={16} className="shrink-0" />
      </Link>
    </HazardFrame>
  );
}

export function SafetyUnknown() {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-[18px] border-[1.5px] border-dashed border-dash bg-surface-soft p-3.5">
      <Icon name="shield" size={20} className="mt-0.5 shrink-0 text-neutral-ink" />
      <span className="text-[13px] font-bold leading-snug text-ink-2">
        Safety alert status unknown — follow official alarms and staff instructions.
      </span>
    </div>
  );
}

const SHOP_TONE = {
  ok: "text-ok",
  soon: "text-busy",
  muted: "text-neutral-ink",
} as const;

export function shopStatusLine(status: ShopStatus): { text: string; tone: keyof typeof SHOP_TONE } {
  switch (status.state) {
    case "open":
      return { text: `Open · until ${formatLocalHM(status.closes_at_local ?? "")}`, tone: "ok" };
    case "closes_soon":
      return { text: `Closes soon · ${formatLocalHM(status.closes_at_local ?? "")}`, tone: "soon" };
    case "closed":
      return {
        text: status.opens_at_local ? `Closed · opens ${formatLocalHM(status.opens_at_local)}` : "Closed for today",
        tone: "muted",
      };
    case "temporarily_closed":
      return { text: "Temporarily closed", tone: "muted" };
    default:
      return { text: "Hours not available", tone: "muted" };
  }
}

export function ShopStatusText({ status, className }: { status: ShopStatus; className?: string }) {
  const line = shopStatusLine(status);
  return <span className={cx("text-xs font-bold", SHOP_TONE[line.tone], className)}>{line.text}</span>;
}

export function ShopStatusDot({ status }: { status: ShopStatus }) {
  const line = shopStatusLine(status);
  return (
    <span className={cx("inline-flex items-center gap-1.5 text-xs font-bold", SHOP_TONE[line.tone])}>
      <span className={cx("h-2 w-2 rounded-full", line.tone === "ok" ? "bg-ok-mark" : line.tone === "soon" ? "bg-busy-mark" : "bg-dash")} />
      {line.text}
    </span>
  );
}

interface Option<T extends string> {
  value: T;
  label: string;
}

interface ChipsProps<T extends string> {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
  wrap?: boolean;
}

export function FilterChips<T extends string>({ label, options, value, onChange, wrap }: ChipsProps<T>) {
  return (
    <div role="group" aria-label={label} className={cx("flex gap-2", wrap ? "flex-wrap" : "scrollbar-none -mx-4 overflow-x-auto px-4")}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={cx(
              "min-h-9 shrink-0 rounded-full px-3.5 text-[13px] md:min-h-[38px] md:px-4",
              active ? "border-0 bg-brand font-bold text-sand" : "border border-line bg-card font-semibold text-ink-2 hover:bg-page",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

interface SegmentedProps<T extends string> extends ChipsProps<T> {
  panelId?: string;
  className?: string;
  stretch?: boolean;
}

export function Segmented<T extends string>({ label, options, value, onChange, panelId, className, stretch }: SegmentedProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const next = (index + step + options.length) % options.length;
    const option = options[next];
    if (!option) return;
    onChange(option.value);
    refs.current[next]?.focus();
  };
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cx("gap-1 rounded-[14px] bg-sand p-1", stretch ? "grid" : "flex flex-wrap", className)}
      style={stretch ? { gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` } : undefined}
    >
      {options.map((o, i) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={panelId}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cx(
              "min-h-[38px] rounded-[10px] border-0 px-3.5 text-[13px] md:px-4",
              active ? "bg-brand font-bold text-sand" : "bg-transparent font-semibold text-muted hover:text-ink",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

interface CanteenSelectProps {
  value: string;
  canteens: Pick<CanteenSummary, "id" | "name">[];
  onChange: (id: string) => void;
  className?: string;
}

export function CanteenSelect({ value, canteens, onChange, className }: CanteenSelectProps) {
  return (
    <label className={cx("relative inline-flex", className)}>
      <span className="sr-only">Canteen</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-10 appearance-none rounded-xl border border-line bg-card py-0 pl-3 pr-9 text-sm font-bold text-ink md:min-h-11 md:pl-3.5"
      >
        {canteens.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <Icon name="chevronDown" size={16} strokeWidth={2.2} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2" />
    </label>
  );
}

interface SearchFieldProps {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
  className?: string;
  inputClassName?: string;
}

export function SearchField({ id, label, value, placeholder, onChange, className, inputClassName }: SearchFieldProps) {
  return (
    <div className={cx("relative", className)}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <Icon name="search" size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
      <input
        id={id}
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={cx(
          "h-11 w-full rounded-[14px] border border-line bg-card pl-[42px] pr-3.5 text-sm text-ink placeholder:text-muted",
          inputClassName,
        )}
      />
    </div>
  );
}
