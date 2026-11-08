import { ApiError } from "@dinemate/api-client";
import { cx, Icon, SampleBadge } from "@dinemate/ui";
import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

export function Page({
  title,
  sample,
  sub,
  actions,
  children,
}: {
  title: string;
  sample?: boolean;
  sub?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main id="main" className="box-border flex min-w-0 flex-[999_1_560px] flex-col gap-6 px-10 pb-10 pt-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2.5">
            <h1 className="m-0 font-display text-[40px] font-extrabold leading-none tracking-[-0.04em]">{title}</h1>
            {sample ? <SampleBadge /> : null}
          </div>
          {sub ? <span className="text-sm text-muted">{sub}</span> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2.5">{actions}</div> : null}
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
    <section className={cx("raised flex min-w-0 flex-col gap-3 rounded-[20px] border border-line bg-card px-[22px] py-5", className)}>
      {title ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="m-0 text-[22px] font-semibold">{title}</h2>
          {aside}
        </div>
      ) : null}
      {children}
    </section>
  );
}

type Tone = "primary" | "secondary" | "danger";

const TONE: Record<Tone, string> = {
  primary: "edge-forest border-0 bg-brand text-sand hover:bg-brand-mid",
  secondary: "border-[1.5px] border-brand bg-card text-ink shadow-[0_3px_0_var(--color-brand)] hover:bg-page",
  danger: "border border-crowd-mark bg-card text-crowd hover:bg-crowd-bg",
};

export function Button({ tone = "secondary", className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Tone }) {
  return (
    <button
      type="button"
      {...props}
      className={cx(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-60",
        TONE[tone],
        className,
      )}
    />
  );
}

const FIELD = "min-h-10 rounded-[10px] border border-line bg-card px-3 text-sm text-ink focus:outline-2 focus:outline-purple";

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
    error: "border-alert-line bg-alert-surface text-crowd",
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

export function useUnsavedGuard(dirty: boolean): void {
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
}
