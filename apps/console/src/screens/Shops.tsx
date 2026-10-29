import {
  api,
  apiMode,
  serverNow,
  useManagedShops,
  useServerNow,
  useSetAvailability,
  useShopEditor,
  useShopMutation,
  type EditableMenuItem,
  type MealPeriod,
  type MenuCategory,
  type MenuItemFields,
  type ShopEditor,
  type ShopState,
} from "@dinemate/api-client";
import { cx, formatAgo, formatClock, formatPrice } from "@dinemate/ui";
import { useCallback, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { Banner, Button, errorText, Field, Page, Panel, Select, TextInput } from "../kit";
import { HoursPanel } from "./ShopHours";

const STATE_LABEL: Record<ShopState, string> = {
  open: "Open",
  closes_soon: "Closes soon",
  closed: "Closed",
  temporarily_closed: "Temporarily closed",
  unknown: "Hours not available",
};

const STATE_STYLE: Record<ShopState, string> = {
  open: "bg-ok-bg text-ok",
  closes_soon: "bg-busy-bg text-busy",
  closed: "bg-neutral text-neutral-ink",
  temporarily_closed: "bg-crowd-bg text-crowd",
  unknown: "bg-neutral text-neutral-ink",
};

const PENDING_LABEL = { new: "New · unpublished", edit: "Edited · unpublished", delete: "Removal · unpublished" } as const;
const PERIODS: MealPeriod[] = ["breakfast", "lunch", "dinner"];
const PERIOD_SHORT: Record<MealPeriod, string> = { breakfast: "B", lunch: "L", dinner: "D" };
const CATEGORIES: { value: MenuCategory | ""; label: string }[] = [
  { value: "", label: "Other" },
  { value: "rice", label: "Rice" },
  { value: "kottu", label: "Kottu" },
  { value: "short_eats", label: "Short eats" },
  { value: "drinks", label: "Drinks" },
];
const CLOSE_FOR = [30, 60, 120, 240];

function StatePill({ state }: { state: ShopState }) {
  return <span className={cx("rounded-full px-2.5 py-1 text-xs font-bold", STATE_STYLE[state])}>{STATE_LABEL[state]}</span>;
}

function PriceInput({ item, editor }: { item: EditableMenuItem; editor: ShopEditor }) {
  const fields = item.draft ?? item.live;
  const [value, setValue] = useState(String(fields?.price_lkr ?? ""));
  const edit = useShopMutation(editor.shop.id, (price: number) => api.editMenuItem(item.id, { price_lkr: price }));
  const commit = () => {
    const price = Number(value);
    if (!Number.isFinite(price) || price < 0 || price === fields?.price_lkr) {
      setValue(String(fields?.price_lkr ?? ""));
      return;
    }
    edit.mutate(price);
  };
  return (
    <span className="inline-flex flex-col gap-0.5">
      <span className="inline-flex items-center gap-1">
        <span className="text-xs text-muted">Rs</span>
        <TextInput
          aria-label={`Price of ${fields?.name ?? "item"}`}
          inputMode="decimal"
          className="w-24 tabular-nums"
          disabled={item.pending === "delete"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
      </span>
      {item.pending === "edit" && item.live && item.draft && item.live.price_lkr !== item.draft.price_lkr ? (
        <span className="text-xs text-muted">Live: {formatPrice(item.live.price_lkr)}</span>
      ) : null}
      {edit.isError ? <span className="text-xs font-semibold text-crowd">{errorText(edit.error)}</span> : null}
    </span>
  );
}

function MenuRow({ item, editor, now }: { item: EditableMenuItem; editor: ShopEditor; now: number }) {
  const fields = item.draft ?? item.live;
  const availability = useSetAvailability(editor.shop.id);
  const remove = useShopMutation(editor.shop.id, () => api.deleteMenuItem(item.id));
  if (!fields) return null;
  const soldOut = !item.is_available;
  return (
    <tr className={cx("border-b border-line-soft align-middle", item.pending === "delete" && "opacity-60")}>
      <td className="py-2.5 pr-2">
        <span className={cx("block text-sm font-bold", item.pending === "delete" && "line-through")}>{fields.name}</span>
        {item.pending !== "none" ? <span className="text-xs font-semibold text-busy">{PENDING_LABEL[item.pending]}</span> : null}
      </td>
      <td className="px-2 text-xs text-muted">
        {PERIODS.filter((p) => fields.periods.includes(p))
          .map((p) => PERIOD_SHORT[p])
          .join(" · ")}
      </td>
      <td className="px-2">
        <PriceInput key={`${item.id}-${fields.price_lkr}`} item={item} editor={editor} />
      </td>
      <td className="px-2">
        {item.pending === "new" ? (
          <span className="text-xs text-muted">After publish</span>
        ) : (
          <span className="flex flex-col gap-0.5">
            <Button
              tone={soldOut ? "danger" : "secondary"}
              aria-pressed={soldOut}
              disabled={availability.isPending}
              onClick={() => availability.mutate({ itemId: item.id, isAvailable: soldOut })}
              className="min-h-9 w-32"
            >
              {soldOut ? "Sold out" : "Available"}
            </Button>
            <span className="text-[11px] text-muted">
              {availability.isError ? errorText(availability.error) : `Updated ${formatAgo(item.availability_updated_at, now)}`}
            </span>
          </span>
        )}
      </td>
      <td className="pl-2 text-right">
        {item.pending !== "delete" ? (
          <Button className="min-h-9" disabled={remove.isPending} onClick={() => remove.mutate(undefined)}>
            Remove
          </Button>
        ) : null}
      </td>
    </tr>
  );
}

function AddItemForm({ editor }: { editor: ShopEditor }) {
  const blank = { name: "", price: "", category: "" as MenuCategory | "", vegetarian: false, periods: ["lunch"] as MealPeriod[] };
  const [form, setForm] = useState(blank);
  const create = useShopMutation(editor.shop.id, (body: MenuItemFields) => api.createMenuItem(editor.shop.id, body));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      {
        name: form.name,
        price_lkr: Number(form.price),
        category: form.category || null,
        dietary_tags: form.vegetarian ? ["vegetarian"] : [],
        periods: form.periods,
      },
      { onSuccess: () => setForm(blank) },
    );
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded-xl bg-page p-3">
      <Field label="New item" className="min-w-48 flex-1">
        <TextInput required maxLength={80} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </Field>
      <Field label="Price (Rs)">
        <TextInput
          required
          inputMode="decimal"
          pattern="\d+(\.\d{1,2})?"
          className="w-28"
          value={form.price}
          onChange={(e) => setForm({ ...form, price: e.target.value })}
        />
      </Field>
      <Field label="Category">
        <Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as MenuCategory | "" })}>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </Select>
      </Field>
      <fieldset className="m-0 flex min-h-10 items-center gap-3 border-0 p-0 text-sm font-semibold">
        <legend className="sr-only">Meal periods</legend>
        {PERIODS.map((p) => (
          <label key={p} className="inline-flex items-center gap-1 capitalize">
            <input
              type="checkbox"
              checked={form.periods.includes(p)}
              onChange={(e) => setForm({ ...form, periods: e.target.checked ? [...form.periods, p] : form.periods.filter((x) => x !== p) })}
            />
            {p}
          </label>
        ))}
        <label className="inline-flex items-center gap-1">
          <input type="checkbox" checked={form.vegetarian} onChange={(e) => setForm({ ...form, vegetarian: e.target.checked })} />
          Vegetarian
        </label>
      </fieldset>
      <Button tone="primary" type="submit" disabled={create.isPending || form.periods.length === 0}>
        Add to draft
      </Button>
      {create.isError ? <span className="w-full text-xs font-semibold text-crowd">{errorText(create.error)}</span> : null}
    </form>
  );
}

function MenuPanel({ editor, now }: { editor: ShopEditor; now: number }) {
  const publish = useShopMutation(editor.shop.id, () => api.publishMenu(editor.shop.id));
  const discard = useShopMutation(editor.shop.id, () => api.discardMenu(editor.shop.id));
  const pending = editor.pending_changes;
  return (
    <Panel
      title="Menu"
      aside={
        <span className="text-xs text-muted">
          {editor.shop.menu_updated_at ? `Published ${formatAgo(editor.shop.menu_updated_at, now)}` : "Not published yet"}
        </span>
      }
    >
      <div
        className={cx(
          "flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3 text-sm font-semibold",
          pending > 0 ? "bg-busy-bg text-busy" : "bg-page text-muted",
        )}
      >
        <span>
          {pending > 0
            ? `${pending} unpublished change${pending === 1 ? "" : "s"}. Students still see the published menu.`
            : "Draft matches the published menu. Sold out changes go live instantly."}
        </span>
        <span className="flex gap-2">
          <Button disabled={pending === 0 || discard.isPending} onClick={() => discard.mutate(undefined)}>
            Discard draft
          </Button>
          <Button tone="primary" disabled={pending === 0 || publish.isPending} onClick={() => publish.mutate(undefined)}>
            {publish.isPending ? "Publishing…" : "Publish"}
          </Button>
        </span>
      </div>
      {publish.isError || discard.isError ? <Banner tone="error">{errorText(publish.error ?? discard.error)}</Banner> : null}
      {editor.items.length === 0 ? (
        <Banner>No menu items yet. Students see "Menu not provided yet".</Banner>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                {["Item", "Meals", "Price", "Availability", ""].map((h, i) => (
                  <th key={i} scope="col" className="border-b border-chip px-2 pb-2 font-semibold first:pl-0">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {editor.items.map((item) => (
                <MenuRow key={item.id} item={item} editor={editor} now={now} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AddItemForm editor={editor} />
    </Panel>
  );
}

function ClosurePanel({ editor }: { editor: ShopEditor }) {
  const [minutes, setMinutes] = useState(60);
  const [reason, setReason] = useState("");
  const close = useShopMutation(editor.shop.id, (body: { until: string | null; reason: string | null }) =>
    api.setShopClosure(editor.shop.id, body),
  );
  const until = editor.temporarily_closed_until;
  const active = until !== null && Date.parse(until) > serverNow();
  return (
    <Panel title="Temporary closure">
      {close.isError ? <Banner tone="error">{errorText(close.error)}</Banner> : null}
      {active ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm font-semibold text-crowd">
            Closed until {formatClock(until)}
            {editor.closure_reason ? ` · ${editor.closure_reason}` : ""}
          </span>
          <Button tone="primary" disabled={close.isPending} onClick={() => close.mutate({ until: null, reason: null })}>
            Reopen now
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Close for">
            <Select value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
              {CLOSE_FOR.map((m) => (
                <option key={m} value={m}>
                  {m < 60 ? `${m} minutes` : `${m / 60} hour${m === 60 ? "" : "s"}`}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Reason (shown to students)" className="min-w-48 flex-1">
            <TextInput maxLength={120} placeholder="e.g. Restocking" value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
          <Button
            tone="danger"
            disabled={close.isPending}
            onClick={() =>
              close.mutate(
                { until: new Date(serverNow() + minutes * 60_000).toISOString(), reason: reason.trim() || null },
                { onSuccess: () => setReason("") },
              )
            }
          >
            Close temporarily
          </Button>
        </div>
      )}
    </Panel>
  );
}

function EditorView({ shopId, onDirty }: { shopId: string; onDirty: (dirty: boolean) => void }) {
  const editor = useShopEditor(shopId);
  const now = useServerNow(15_000);
  if (editor.isError) return <Banner tone="error">{errorText(editor.error)}</Banner>;
  if (!editor.data) return <div aria-busy="true" className="h-40 rounded-2xl bg-card" />;
  const data = editor.data;
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 text-xl font-extrabold">{data.shop.name}</h2>
        <StatePill state={data.shop.status.state} />
        <span className="text-sm text-muted">{data.shop.canteen_name}</span>
      </div>
      <MenuPanel editor={data} now={now} />
      <ClosurePanel editor={data} />
      <HoursPanel editor={data} onDirty={onDirty} />
    </>
  );
}

export function ShopsScreen() {
  const shops = useManagedShops();
  const [params, setParams] = useSearchParams();
  const [dirty, setDirty] = useState(false);
  const onDirty = useCallback((value: boolean) => setDirty(value), []);
  const items = shops.data?.items ?? [];
  const selected = params.get("shop") ?? items[0]?.shop.id;
  const pick = (id: string) => {
    if (dirty && !window.confirm("You have unsaved opening hours. Leave without saving?")) return;
    setParams({ shop: id });
  };
  const sample = apiMode() === "sample";
  return (
    <Page
      title="Shops & menus"
      sample={items.some((s) => s.shop.is_sample)}
      sub="Edits go to a draft until you publish. Sold out is instant."
    >
      {sample ? <Banner>Editing shops needs the real API. Start it with pnpm stack:up, then pnpm dev:console:api.</Banner> : null}
      {shops.isError && !sample ? <Banner tone="error">{errorText(shops.error)}</Banner> : null}
      {items.length > 1 ? (
        <nav aria-label="Shops" className="flex flex-wrap gap-2">
          {items.map(({ shop, pending_changes }) => (
            <button
              key={shop.id}
              type="button"
              aria-current={shop.id === selected ? "page" : undefined}
              onClick={() => pick(shop.id)}
              className={cx(
                "inline-flex min-h-10 items-center gap-2 rounded-[10px] border px-3 text-sm font-semibold",
                shop.id === selected ? "border-brand bg-brand text-white" : "border-line bg-card text-ink hover:bg-page",
              )}
            >
              {shop.name}
              <span className="text-xs opacity-80">{shop.canteen_name}</span>
              {pending_changes > 0 ? (
                <span className="rounded-full bg-busy-bg px-1.5 text-xs font-bold text-busy">{pending_changes}</span>
              ) : null}
            </button>
          ))}
        </nav>
      ) : null}
      {shops.isSuccess && items.length === 0 ? <Banner>No shops are assigned to your account yet.</Banner> : null}
      {selected && items.length > 0 ? <EditorView key={selected} shopId={selected} onDirty={onDirty} /> : null}
    </Page>
  );
}
