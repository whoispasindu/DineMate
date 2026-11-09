import { useStaffSheet, type StaffUser } from "@dinemate/api-client";
import { formatDateLine, formatWeekday } from "@dinemate/ui";
import { Link, useParams } from "react-router";
import { Banner, Button, errorText, Page, Panel, Skeleton } from "../kit";
import { AREAS, hoursMinutes, MethodChip, OwnerOnly, totalMinutes } from "../staff";

export function StaffSheetScreen({ user }: { user: StaffUser }) {
  const { staffId } = useParams();
  const owner = user.role === "owner";
  const sheet = useStaffSheet(owner ? staffId : undefined);
  const data = sheet.data;
  if (!owner) {
    return (
      <Page title="Worker sheet" sub="Owner only">
        <OwnerOnly what="A worker's sheet" />
      </Page>
    );
  }
  return (
    <Page
      title={data ? data.staff.display_name : "Worker sheet"}
      sub={data ? `${data.venue_name} · last 7 days` : "Worker sheet"}
      sample={data?.staff.is_sample}
      actions={
        <span className="flex gap-2.5 print:hidden">
          <Link to="/staff" className="inline-flex min-h-10 items-center px-2 text-sm font-bold text-ink-2 no-underline hover:underline">
            Back to Staff
          </Link>
          <Button tone="primary" disabled={!data} onClick={() => window.print()}>
            Print
          </Button>
        </span>
      }
    >
      {sheet.isError ? <Banner tone="error">{errorText(sheet.error)}</Banner> : null}
      {!data ? (
        <Skeleton className="h-[320px]" />
      ) : (
        <>
          <Panel>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="font-bold">{data.staff.role_label || "Staff"}</span>
              <MethodChip method={data.staff.method} badge={data.staff.badge_code} />
              {data.staff.till_code ? <span className="text-muted">Till code {data.staff.till_code}</span> : null}
              <span className="text-muted">
                {data.staff.consent_at ? `Consent recorded ${formatDateLine(data.staff.consent_at)}` : "No consent recorded"}
              </span>
            </div>
            <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Time by area and items served per day">
              <table className="w-full min-w-[520px] border-collapse text-sm">
                <thead>
                  <tr className="text-left text-[13px] text-muted">
                    <th className="py-2 font-semibold">Day</th>
                    {AREAS.map((a) => (
                      <th key={a.key} className="py-2 text-right font-semibold">
                        {a.label}
                      </th>
                    ))}
                    <th className="py-2 text-right font-semibold">Total</th>
                    <th className="py-2 text-right font-semibold">Items served</th>
                  </tr>
                </thead>
                <tbody>
                  {data.days.map((d) => (
                    <tr key={d.day} className="border-t border-line-soft">
                      <td className="py-2.5 font-semibold">
                        {formatWeekday(`${d.day}T12:00:00+05:30`)} {d.day.slice(8)}/{d.day.slice(5, 7)}
                      </td>
                      {AREAS.map((a) => (
                        <td key={a.key} className="py-2.5 text-right">
                          {d.minutes[a.key] > 0 ? hoursMinutes(d.minutes[a.key]) : "—"}
                        </td>
                      ))}
                      <td className="py-2.5 text-right font-bold">{hoursMinutes(totalMinutes(d.minutes))}</td>
                      <td className="py-2.5 text-right">{d.items}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <p className="m-0 max-w-2xl text-xs leading-relaxed text-muted">
            Times are estimates from the café camera, counted only inside work areas, and rounded to the minute. Items come from the till by
            cashier code. This record is kept for {data.kept_days} days and then deleted. You can ask the owner to correct it, or withdraw
            consent at any time; withdrawing deletes your face template and this history.
          </p>
        </>
      )}
    </Page>
  );
}
