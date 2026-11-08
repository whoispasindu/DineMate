import { ApiError } from "@dinemate/api-client";
import { cx, Icon, SampleBadge } from "@dinemate/ui";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function Page({
  title,
  sub,
  sample,
  actions,
  children,
}: {
  title: string;
  sub?: ReactNode;
  sample?: boolean;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main id="main" className="box-border flex min-w-0 flex-1 flex-col gap-5 px-4 pb-28 pt-5 md:gap-6 md:px-9 md:pb-10 md:pt-7">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          {sub ? <span className="text-[13px] font-semibold text-muted">{sub}</span> : null}
          <h1 className="m-0 font-display text-[32px] font-extrabold leading-none tracking-[-0.04em] md:text-[38px]">{title}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {actions}
          {sample ? <SampleBadge /> : null}
        </div>
      </header>
      {children}
    </main>
  );
}

export function Panel({
  title,
  aside,
  children,
  className,
}: {
  title?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("raised flex min-w-0 flex-col gap-3 rounded-[20px] border border-line bg-card px-5 py-[18px]", className)}>
      {title ? (
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="m-0 text-[22px] font-semibold">{title}</h2>
          {aside}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Kpi({
  label,
  value,
  note,
  hero,
  tone,
}: {
  label: string;
  value: ReactNode;
  note: string;
  hero?: boolean;
  tone?: "ok" | "alert";
}) {
  return (
    <div
      className={cx(
        "flex min-w-[180px] flex-1 flex-col gap-2 rounded-[20px] px-5 py-[18px]",
        hero ? "slab bg-brand text-on-dark" : "raised border border-line bg-card",
      )}
    >
      <span className={cx("text-[13px] font-semibold", hero ? "text-on-dark-faint" : "text-muted")}>{label}</span>
      <span
        className={cx(
          "font-display text-[36px] font-extrabold leading-none tracking-[-0.04em]",
          tone === "ok" && "text-ok-mark",
          tone === "alert" && "text-crowd-mark",
        )}
      >
        {value}
      </span>
      <span className={cx("text-[13px]", hero ? "text-on-dark-faint" : "text-muted")}>{note}</span>
    </div>
  );
}

type Tone = "primary" | "accent" | "secondary";

const TONE: Record<Tone, string> = {
  primary: "edge-forest border-0 bg-brand text-on-dark hover:bg-brand-mid",
  accent: "border-0 bg-purple text-white shadow-[0_3px_0_var(--color-purple-deep)] hover:bg-purple-ink",
  secondary: "border-[1.5px] border-brand bg-card text-ink shadow-[0_3px_0_var(--color-brand)] hover:bg-page",
};

export function Button({ tone = "secondary", className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Tone }) {
  return (
    <button
      type="button"
      {...props}
      className={cx(
        "inline-flex min-h-10 items-center justify-center gap-2 whitespace-nowrap rounded-xl px-4 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-60",
        TONE[tone],
        className,
      )}
    />
  );
}

const FIELD = "min-h-10 rounded-[10px] border border-line bg-card px-3 text-sm text-ink";

export function Field({ label, hint, children, className }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <label className={cx("flex flex-col gap-1.5 text-[13px] font-semibold text-ink-2", className)}>
      {label}
      {children}
      {hint ? <span className="text-xs font-normal text-muted">{hint}</span> : null}
    </label>
  );
}

export function TextInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(FIELD, className)} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(FIELD, className)} />;
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.status === 403 ? `Not allowed: ${error.message}` : error.message;
  return "Something went wrong. Try again.";
}

export function Banner({ tone = "info", children }: { tone?: "info" | "error" | "ok"; children: ReactNode }) {
  const style = {
    info: "border-dashed border-dash bg-card text-ink-2",
    error: "border-crowd-bg bg-crowd-bg text-crowd",
    ok: "border-ok-bg bg-ok-bg text-ok",
  }[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx("flex items-start gap-2.5 rounded-2xl border p-4 text-sm font-semibold", style)}
    >
      <Icon name={tone === "ok" ? "checkCircle" : tone === "error" ? "warning" : "info"} size={18} className="mt-px shrink-0" />
      <span>{children}</span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("rounded-[20px] bg-line-soft motion-safe:animate-pulse", className)} />;
}
