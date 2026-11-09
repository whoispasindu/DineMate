import {
  useBusinessSettings,
  useCreateStaff,
  useRecordConsent,
  useRemoveStaff,
  useSaveBusinessSettings,
  useServerNow,
  useStaff,
  useStaffAudit,
  useUpdateStaff,
  useWithdrawConsent,
  type StaffMember,
  type StaffMethod,
  type StaffUser,
} from "@dinemate/api-client";
import { cx, formatDateLine, formatDayStamp, TIME_ZONE } from "@dinemate/ui";
import { useState } from "react";
import { Banner, Button, errorText, Field, Page, Panel, Select, Skeleton, TextInput } from "../kit";
import { MethodChip, OwnerOnly } from "../staff";
import { useVenue } from "../venue";

const NOTICE_VERSION = "staff-notice-v1";
const dayFormat = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" });

function badgeValue(text: string): number | null {
  return text.trim() === "" ? null : Number(text);
}

function badgeOk(method: StaffMethod, text: string): boolean {
  if (text.trim() === "") return method === "face";
  const n = Number(text);
  return Number.isInteger(n) && n >= 0 && n <= 249;
}

function AddWorker({ venueId }: { venueId: string }) {
  const create = useCreateStaff(venueId);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [method, setMethod] = useState<StaffMethod>("badge");
  const [badge, setBadge] = useState("");
  const [till, setTill] = useState("");
  const valid = name.trim() !== "" && badgeOk(method, badge);
  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-[14px] bg-page p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid) return;
        create.mutate(
          {
            display_name: name.trim(),
            role_label: role.trim(),
            method,
            badge_code: badgeValue(badge),
            till_code: till.trim() || null,
          },
          {
            onSuccess: () => {
              setName("");
              setRole("");
              setBadge("");
              setTill("");
            },
          },
        );
      }}
    >
      <Field label="Name shown in reports" className="w-[200px]">
        <TextInput value={name} maxLength={40} onChange={(e) => setName(e.target.value)} placeholder="Barista 3" />
      </Field>
      <Field label="Role" className="w-[150px]">
        <TextInput value={role} maxLength={40} onChange={(e) => setRole(e.target.value)} placeholder="Barista" />
      </Field>
      <Field label="Recognised by" className="w-[140px]">
        <Select value={method} onChange={(e) => setMethod(e.target.value as StaffMethod)}>
          <option value="badge">Badge</option>
          <option value="face">Face</option>
        </Select>
      </Field>
      <Field label="Badge code" hint="0 to 249" className="w-[110px]">
        <TextInput inputMode="numeric" value={badge} onChange={(e) => setBadge(e.target.value)} />
      </Field>
      <Field label="Till code" className="w-[110px]">
        <TextInput value={till} maxLength={20} onChange={(e) => setTill(e.target.value)} placeholder="B3" />
      </Field>
      <Button type="submit" tone="primary" disabled={!valid || create.isPending}>
        Add worker
      </Button>
      {create.isError ? (
        <div className="w-full">
          <Banner tone="error">{errorText(create.error)}</Banner>
        </div>
      ) : null}
    </form>
  );
}

function Consent({ member, venueId, today }: { member: StaffMember; venueId: string; today: string }) {
  const record = useRecordConsent(venueId);
  const withdraw = useWithdrawConsent(venueId);
  const [open, setOpen] = useState(false);
  const [version, setVersion] = useState(NOTICE_VERSION);
  const [signed, setSigned] = useState(today);
  const [confirm, setConfirm] = useState(false);
  const error = record.error ?? withdraw.error;
  if (member.consent_at) {
    return (
      <span className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] text-ok">
          Signed {formatDateLine(member.consent_at)} · {member.consent_version}
        </span>
        {confirm ? (
          <>
            <Button className="min-h-9" disabled={withdraw.isPending} onClick={() => withdraw.mutate(member.id)}>
              Withdraw and delete data<span className="sr-only"> for {member.display_name}</span>
            </Button>
            <Button className="min-h-9" onClick={() => setConfirm(false)}>
              Keep
            </Button>
          </>
        ) : (
          <Button className="min-h-9" onClick={() => setConfirm(true)}>
            Withdraw consent<span className="sr-only"> for {member.display_name}</span>
          </Button>
        )}
        {error ? <span className="text-[13px] text-crowd">{errorText(error)}</span> : null}
      </span>
    );
  }
  if (!open) {
    return (
      <span className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] text-busy">No consent · not recognised</span>
        <Button className="min-h-9" onClick={() => setOpen(true)}>
          Record consent<span className="sr-only"> for {member.display_name}</span>
        </Button>
      </span>
    );
  }
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        record.mutate({ staffId: member.id, body: { version, signed_on: signed } }, { onSuccess: () => setOpen(false) });
      }}
    >
      <Field label="Notice version" className="w-[150px]">
        <TextInput value={version} maxLength={40} onChange={(e) => setVersion(e.target.value)} />
      </Field>
      <Field label="Signed on" className="w-[160px]">
        <TextInput type="date" value={signed} max={today} onChange={(e) => setSigned(e.target.value)} />
      </Field>
      <Button type="submit" tone="primary" className="min-h-10" disabled={!version.trim() || !signed || record.isPending}>
        Save consent
      </Button>
      <Button className="min-h-10" onClick={() => setOpen(false)}>
        Cancel
      </Button>
      {error ? <span className="w-full text-[13px] text-crowd">{errorText(error)}</span> : null}
    </form>
  );
}

function Recognition({ member, venueId }: { member: StaffMember; venueId: string }) {
  const update = useUpdateStaff(venueId);
  const [editing, setEditing] = useState(false);
  const [method, setMethod] = useState<StaffMethod>(member.method);
  const [badge, setBadge] = useState(member.badge_code?.toString() ?? "");
  const [till, setTill] = useState(member.till_code ?? "");
  if (!editing) {
    return (
      <span className="flex flex-wrap items-center gap-2 text-[13px] text-muted">
        <MethodChip method={member.method} badge={member.badge_code} />
        {member.method === "face" ? (member.has_template ? "Face enrolled" : "Not enrolled yet") : null}
        {member.till_code ? <span className="font-mono">till {member.till_code}</span> : <span>no till code</span>}
        <button
          type="button"
          className="font-bold text-purple-ink underline-offset-2 hover:underline"
          onClick={() => setEditing(true)}
          aria-label={`Change recognition for ${member.display_name}`}
        >
          Change
        </button>
      </span>
    );
  }
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate(
          { staffId: member.id, body: { method, badge_code: badgeValue(badge), till_code: till.trim() || null } },
          { onSuccess: () => setEditing(false) },
        );
      }}
    >
      <Field label="Recognised by" className="w-[130px]">
        <Select value={method} onChange={(e) => setMethod(e.target.value as StaffMethod)}>
          <option value="badge">Badge</option>
          <option value="face">Face</option>
        </Select>
      </Field>
      <Field label="Badge code" className="w-[100px]">
        <TextInput inputMode="numeric" value={badge} onChange={(e) => setBadge(e.target.value)} />
      </Field>
      <Field label="Till code" className="w-[100px]">
        <TextInput value={till} maxLength={20} onChange={(e) => setTill(e.target.value)} />
      </Field>
      <Button type="submit" tone="primary" disabled={!badgeOk(method, badge) || update.isPending}>
        Save
      </Button>
      <Button onClick={() => setEditing(false)}>Cancel</Button>
      {update.isError ? <span className="w-full text-[13px] text-crowd">{errorText(update.error)}</span> : null}
    </form>
  );
}

function Remove({ member, venueId }: { member: StaffMember; venueId: string }) {
  const remove = useRemoveStaff(venueId);
  const [confirm, setConfirm] = useState(false);
  if (!confirm) {
    return (
      <Button className="min-h-9" onClick={() => setConfirm(true)}>
        Remove<span className="sr-only"> {member.display_name}</span>
      </Button>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-2">
      <span className="text-[13px] text-crowd">Deletes their template and history. Till orders stay, unnamed.</span>
      <Button className="min-h-9" disabled={remove.isPending} onClick={() => remove.mutate(member.id)}>
        Remove {member.display_name}
      </Button>
      <Button className="min-h-9" onClick={() => setConfirm(false)}>
        Cancel
      </Button>
      {remove.isError ? <span className="text-[13px] text-crowd">{errorText(remove.error)}</span> : null}
    </span>
  );
}

function Roster({ venueId, today }: { venueId: string; today: string }) {
  const staff = useStaff(venueId);
  const items = staff.data?.items ?? [];
  return (
    <Panel title="Staff and consent" aside={<span className="text-[13px] text-muted">{items.length} people</span>}>
      {staff.isError ? <Banner tone="error">{errorText(staff.error)}</Banner> : null}
      {!staff.data ? <Skeleton className="h-[200px]" /> : null}
      <ul className="m-0 flex list-none flex-col p-0">
        {items.map((m, i) => (
          <li key={m.id} className={cx("flex flex-col gap-2 py-3.5", i > 0 && "border-t border-line-soft")}>
            <span className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-[15px] font-bold">
                {m.display_name} <span className="font-normal text-muted">· {m.role_label || "Staff"}</span>
                {m.is_sample ? (
                  <span className="ml-2 rounded-full bg-chip px-2 py-0.5 text-xs font-semibold text-neutral-ink">Sample</span>
                ) : null}
              </span>
              <Remove member={m} venueId={venueId} />
            </span>
            <Recognition member={m} venueId={venueId} />
            <Consent member={m} venueId={venueId} today={today} />
          </li>
        ))}
      </ul>
      <AddWorker venueId={venueId} />
    </Panel>
  );
}

function Enrolment({ facesEnabled }: { facesEnabled: boolean }) {
  return (
    <Panel title="Setting up recognition">
      <ol className="m-0 flex list-decimal flex-col gap-2.5 pl-5 text-sm leading-relaxed text-ink-2">
        <li>Give the worker the staff notice and consent form from the privacy kit, and record their signed consent here.</li>
        <li>
          <span className="font-semibold">Badge:</span> on the café computer run{" "}
          <code className="font-mono text-[13px]">uv run python -m vision.badges 11</code> with their badge code, print it at about 6 cm,
          and wear it on the chest.
        </li>
        <li>
          <span className="font-semibold">Face:</span>{" "}
          {facesEnabled ? (
            <>
              on the café computer run <code className="font-mono text-[13px]">uv run python -m vision.enrol --email you@example.com</code>.
              It takes five shots and sends only a 128-number template. No photo is kept.
            </>
          ) : (
            <>face templates are off on this server (cloud or no template key). Use badges, or run DineMate on a local server.</>
          )}
        </li>
        <li>Mark the counter, kitchen and floor work areas on the camera. People are only recognised inside them.</li>
      </ol>
    </Panel>
  );
}

function Kept({ owner }: { owner: boolean }) {
  const settings = useBusinessSettings();
  const save = useSaveBusinessSettings();
  const [days, setDays] = useState<number | null>(null);
  const current = days ?? settings.data?.staff_retention_days ?? 60;
  const rows: [string, string][] = [
    ["Video and photos", "Never stored"],
    ["Customer faces", "Never matched, blurred in live view"],
    ["Face templates", settings.data?.faces_enabled ? "Encrypted, on this server only" : "Off on this server"],
    ["Time in work areas", `${settings.data?.staff_retention_days ?? 60} days, then deleted`],
  ];
  return (
    <Panel title="What we keep">
      {save.isError ? <Banner tone="error">{errorText(save.error)}</Banner> : null}
      {save.isSuccess ? <Banner tone="ok">Saved. Older staff records are deleted automatically.</Banner> : null}
      <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
        {rows.map(([label, value]) => (
          <li key={label} className="flex justify-between gap-3">
            <span className="font-semibold">{label}</span>
            <span className="text-right text-muted">{value}</span>
          </li>
        ))}
      </ul>
      {owner ? (
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Keep staff time for (days)" hint="Between 7 and 365 days" className="w-[220px]">
            <TextInput type="number" min={7} max={365} value={current} onChange={(e) => setDays(Number(e.target.value))} />
          </Field>
          <Button
            tone="primary"
            disabled={save.isPending || current < 7 || current > 365}
            onClick={() => save.mutate({ staff_retention_days: current })}
          >
            Save
          </Button>
        </div>
      ) : null}
    </Panel>
  );
}

function Views({ now }: { now: number }) {
  const audit = useStaffAudit();
  const items = audit.data?.items ?? [];
  return (
    <Panel title="Who viewed staff reports" aside={<span className="text-[13px] text-muted">Every view is recorded</span>}>
      {audit.isError ? <Banner tone="error">{errorText(audit.error)}</Banner> : null}
      {audit.data && items.length === 0 ? <p className="m-0 text-sm text-muted">Nobody has opened a staff report yet.</p> : null}
      <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
        {items.slice(0, 10).map((e) => (
          <li key={`${e.at}-${e.entity_id}`} className="flex flex-wrap justify-between gap-2">
            <span className="font-semibold">
              {e.actor}{" "}
              <span className="font-normal text-muted">
                {e.entity_id.startsWith("v-") ? "opened the staff report" : "opened a worker sheet"}
              </span>
            </span>
            <span className="text-muted">{Date.parse(e.at) > now - 86_400_000 ? formatDayStamp(e.at) : formatDateLine(e.at)}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function PrivacyScreen({ user }: { user: StaffUser }) {
  const { venue } = useVenue();
  const now = useServerNow(60_000);
  const settings = useBusinessSettings();
  const owner = user.role === "owner";
  if (!owner) {
    return (
      <Page title="Privacy & consent" sub="Owner only">
        <OwnerOnly what="Staff consent and enrolment" />
      </Page>
    );
  }
  const today = dayFormat.format(new Date(now));
  return (
    <Page title="Privacy & consent" sub="Staff opt in · customers are never identified" sample={venue?.is_sample}>
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex min-w-0 flex-[1.6_1_560px] flex-col gap-4">{venue ? <Roster venueId={venue.id} today={today} /> : null}</div>
        <div className="flex min-w-[300px] flex-[1_1_340px] flex-col gap-4">
          <Enrolment facesEnabled={settings.data?.faces_enabled ?? false} />
          <Kept owner={owner} />
          <Views now={now} />
        </div>
      </div>
      <p className="m-0 max-w-3xl text-xs leading-relaxed text-muted">
        The privacy kit (staff notice, consent form, impact assessment and retention guide) is in docs/business/privacy. It is a starting
        point, not legal advice: review it locally before use.
      </p>
    </Page>
  );
}
