import { useImportTill, useSales, type SalesDay, type TillImportResult } from "@dinemate/api-client";
import { cx, formatPrice } from "@dinemate/ui";
import { useState, type ChangeEvent } from "react";
import { Banner, Button, errorText, Kpi, Page, Panel, Skeleton } from "../kit";
import { useVenue } from "../venue";

const COLUMNS = "order_id,time,cashier,item,qty,unit_price";
const EXAMPLE = `${COLUMNS}\nA-1001,2026-11-20 12:04,B1,Latte,2,650\nA-1001,2026-11-20 12:04,B1,Croissant,1,400`;
const MAX_BYTES = 5_000_000;

function hourLabel(hour: number): string {
  if (hour === 12) return "12p";
  return hour > 12 ? String(hour - 12) : String(hour);
}

function OrdersByHour({ data }: { data: SalesDay }) {
  const active = data.by_hour.filter((h) => h.orders > 0);
  const first = active[0]?.hour ?? 7;
  const last = active.at(-1)?.hour ?? 20;
  const hours = data.by_hour.filter((h) => h.hour >= first && h.hour <= last);
  const top = Math.max(1, ...hours.map((h) => h.orders));
  return (
    <Panel title="Orders by hour" className="flex-[1.5_1_480px]">
      {active.length === 0 ? <p className="m-0 text-sm text-muted">No orders yet today.</p> : null}
      <ul className="m-0 flex h-[220px] list-none items-end gap-2 p-0">
        {active.length > 0
          ? hours.map((h) => (
              <li key={h.hour} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
                <span className="text-xs font-semibold text-muted">{h.orders}</span>
                <div
                  aria-hidden="true"
                  className={cx("w-full rounded-t-md rounded-b-sm", h.orders === top ? "bg-purple" : "bg-brand")}
                  style={{ height: `${Math.max(3, (h.orders / top) * 170)}px` }}
                />
                <span className="text-xs text-muted">{hourLabel(h.hour)}</span>
                <span className="sr-only">
                  {h.hour}:00, {h.orders} orders
                </span>
              </li>
            ))
          : null}
      </ul>
    </Panel>
  );
}

function ByCashier({ data }: { data: SalesDay }) {
  const top = Math.max(1, ...data.by_cashier.map((c) => c.total_items));
  return (
    <Panel title="Items per cashier" aside={<span className="text-[13px] text-muted">Matched by till code</span>}>
      {data.by_cashier.length === 0 ? <p className="m-0 text-sm text-muted">No cashier codes in today's orders.</p> : null}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {data.by_cashier.map((c) => (
          <li key={c.cashier} className="flex flex-col gap-1.5">
            <span className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-bold">
                {c.staff_name ?? "Not on the staff list"} <span className="font-mono text-xs font-normal text-muted">{c.cashier}</span>
              </span>
              <span>
                <span className="font-bold">{c.total_items}</span> <span className="text-muted">items · {c.orders} orders</span>
              </span>
            </span>
            <span aria-hidden="true" className="h-2.5 overflow-hidden rounded-full bg-track">
              <span className="block h-full rounded-full bg-brand" style={{ width: `${(c.total_items / top) * 100}%` }} />
            </span>
            <span className="text-[13px] text-ink-2">{c.items.map((i) => `${i.name} ${i.qty}`).join(" · ")}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Outcome({ result }: { result: TillImportResult }) {
  return (
    <div className="flex flex-col gap-2 rounded-[14px] bg-page p-4 text-sm" role="status">
      <span className="font-bold">
        {result.saved ? "Imported. " : "Checked, nothing saved yet. "}
        {result.rows} rows · {result.orders} orders · {result.new_orders} new · {result.duplicates} already imported
      </span>
      {result.matched_cashiers.length > 0 ? <span>Matched to staff: {result.matched_cashiers.join(", ")}</span> : null}
      {result.unmatched_cashiers.length > 0 ? (
        <span className="text-busy">
          Not on the staff list: {result.unmatched_cashiers.join(", ")}. Add their till code in Privacy &amp; consent, or they stay as
          anonymous sales.
        </span>
      ) : null}
      {result.errors.length > 0 ? (
        <ul className="m-0 flex list-disc flex-col gap-0.5 pl-5 text-crowd">
          {result.errors.slice(0, 8).map((e) => (
            <li key={e}>{e}</li>
          ))}
          {result.errors.length > 8 ? <li>and {result.errors.length - 8} more</li> : null}
        </ul>
      ) : null}
    </div>
  );
}

function TillImport({ venueId }: { venueId: string }) {
  const importTill = useImportTill(venueId);
  const [csv, setCsv] = useState("");
  const [name, setName] = useState<string | null>(null);
  const [tooBig, setTooBig] = useState(false);
  const checked = importTill.data && !importTill.data.saved ? importTill.data : null;
  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    importTill.reset();
    if (!file) return;
    setTooBig(file.size > MAX_BYTES);
    if (file.size > MAX_BYTES) return;
    setName(file.name);
    void file.text().then(setCsv);
  };
  return (
    <Panel title="Import till file" aside={<span className="text-[13px] text-muted">CSV export from your till</span>}>
      <p className="m-0 text-sm text-ink-2">
        One row per item, with the columns <code className="font-mono text-[13px]">{COLUMNS}</code>. Times are café time. Orders already
        imported are skipped, so you can import the same day again.
      </p>
      <details className="text-[13px] text-muted">
        <summary className="cursor-pointer font-semibold">Example</summary>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-page p-3 font-mono text-xs text-ink-2">{EXAMPLE}</pre>
      </details>
      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex min-h-10 cursor-pointer items-center rounded-xl border-[1.5px] border-brand bg-card px-4 text-sm font-bold shadow-[0_3px_0_var(--color-brand)] focus-within:outline focus-within:outline-2 focus-within:outline-purple hover:bg-page">
          Choose CSV file
          <input type="file" accept=".csv,text/csv" className="sr-only" onChange={pick} />
        </label>
        <span className="text-sm text-muted">{name ?? "No file chosen"}</span>
      </div>
      {tooBig ? <Banner tone="error">That file is over 5 MB. Export one week at a time.</Banner> : null}
      {importTill.isError ? <Banner tone="error">{errorText(importTill.error)}</Banner> : null}
      {importTill.data ? <Outcome result={importTill.data} /> : null}
      <div className="flex flex-wrap gap-2.5">
        <Button disabled={!csv || importTill.isPending} onClick={() => importTill.mutate({ csv, dryRun: true })}>
          Check file
        </Button>
        <Button
          tone="primary"
          disabled={!checked || checked.new_orders === 0 || importTill.isPending}
          onClick={() => importTill.mutate({ csv, dryRun: false })}
        >
          {checked ? `Import ${checked.new_orders} new orders` : "Import"}
        </Button>
      </div>
    </Panel>
  );
}

export function SalesScreen() {
  const { venue } = useVenue();
  const sales = useSales(venue?.id);
  const data = sales.data;
  return (
    <Page title="Sales" sub="Today · from your till files" sample={data?.is_sample}>
      {sales.isError ? <Banner tone="error">{errorText(sales.error)}</Banner> : null}
      {!data ? (
        <div role="status" aria-label="Loading sales" className="flex flex-col gap-4">
          <Skeleton className="h-[118px]" />
          <Skeleton className="h-[280px]" />
        </div>
      ) : (
        <>
          <section aria-label="Key figures" className="flex flex-wrap gap-4">
            <Kpi hero label="Orders today" value={data.orders} note={`${data.items} items`} />
            <Kpi
              label="Average order"
              value={
                <span className="font-mono text-[30px]">
                  {data.average_order !== null ? formatPrice(Math.round(data.average_order)) : "—"}
                </span>
              }
              note="Per order"
            />
            <Kpi
              label="Takings"
              value={<span className="font-mono text-[30px]">{formatPrice(Math.round(data.revenue))}</span>}
              note="From imported orders"
            />
            <Kpi
              label="Top item"
              value={data.top_items[0]?.name ?? "—"}
              note={data.top_items[0] ? `${data.top_items[0].qty} sold` : "No items yet"}
              tone="ok"
            />
          </section>
          <div className="flex flex-wrap items-start gap-4">
            <OrdersByHour data={data} />
            <div className="flex min-w-[300px] flex-[1_1_360px] flex-col gap-4">
              <ByCashier data={data} />
            </div>
          </div>
        </>
      )}
      {venue ? <TillImport venueId={venue.id} /> : null}
    </Page>
  );
}
