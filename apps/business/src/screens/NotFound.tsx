import { Icon } from "@dinemate/ui";
import { Page } from "../kit";

export function NotFoundScreen() {
  return (
    <Page title="Not found">
      <div className="flex max-w-xl items-start gap-3 rounded-2xl border border-dashed border-dash bg-card p-5">
        <Icon name="info" size={20} className="mt-0.5 shrink-0 text-muted" />
        <p className="m-0 text-sm leading-relaxed text-ink-2">There is no page at this address.</p>
      </div>
    </Page>
  );
}
