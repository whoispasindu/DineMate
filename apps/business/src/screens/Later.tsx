import { Icon } from "@dinemate/ui";
import { useLocation } from "react-router";
import { NAV } from "../layout";
import { Page } from "../kit";

const WHAT: Record<string, string> = {
  "/staff":
    "Time each worker spends at the counter, kitchen and floor, items served from the till, and counter coverage. Staff opt in with written consent; customers are never recognised.",
  "/sales": "Orders per hour, average order and items sold per cashier, from a till CSV first and then a real till connection.",
  "/privacy": "Staff consent records, face or badge enrolment, what each worker can see about themselves, and the staff notice templates.",
};

export function LaterScreen() {
  const { pathname } = useLocation();
  const item = NAV.find((n) => n.to === pathname);
  return (
    <Page title={item?.label ?? "Not found"} sub={item ? "Coming in Phase 9" : undefined}>
      <div className="flex max-w-xl items-start gap-3 rounded-2xl border border-dashed border-dash bg-card p-5">
        <Icon name="info" size={20} className="mt-0.5 shrink-0 text-muted" />
        <p className="m-0 text-sm leading-relaxed text-ink-2">
          {item ? (WHAT[pathname] ?? "Planned for Phase 9.") : "There is no page at this address."}
        </p>
      </div>
    </Page>
  );
}
