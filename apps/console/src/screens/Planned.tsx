import { Icon } from "@dinemate/ui";
import { useLocation } from "react-router";
import { NAV } from "../layout";

export function PlannedScreen() {
  const { pathname } = useLocation();
  const item = NAV.find((n) => n.to === pathname);
  return (
    <main id="main" className="box-border flex min-w-0 flex-[999_1_560px] flex-col gap-5 px-8 pb-10 pt-7">
      <h1 className="m-0 font-display text-[40px] font-extrabold leading-none tracking-[-0.04em]">{item?.label ?? "Not found"}</h1>
      <div className="flex max-w-xl items-start gap-3 rounded-2xl border border-dashed border-dash bg-card p-5">
        <Icon name="info" size={20} className="mt-0.5 shrink-0 text-muted" />
        <p className="m-0 text-sm leading-relaxed text-ink-2">
          {item
            ? "This page is planned for a later milestone (development plan, Section 13.6). The Overview shows the live data it will build on."
            : "There is no console page at this address."}
        </p>
      </div>
    </main>
  );
}
