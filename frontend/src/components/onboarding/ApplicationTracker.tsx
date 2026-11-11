"use client";

import clsx from "clsx";
import { CheckCircle2, Clock } from "lucide-react";
import { Badge, Card, CardHeader } from "@/components/ui";
import { APPLICATION_STATUS_META } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type { ApplicationDetail } from "@/lib/types";

const STAGES = [
  { key: "DRAFT", label: "Draft" },
  { key: "SUBMITTED", label: "Submitted" },
  { key: "IN_REVIEW", label: "Review" },
  { key: "KYC_APPROVED", label: "KYC approved" },
  { key: "TRAINING_IN_PROGRESS", label: "15h Training" },
  { key: "CERTIFIED", label: "Certified" },
];

function stageIndex(status: string): number {
  if (status === "DRAFT") return 0;
  if (status === "SUBMITTED" || status === "REWORK_SUBMITTED") return 1;
  if (status === "IN_REVIEW" || status === "NEEDS_MORE_INFO") return 2;
  if (status === "KYC_APPROVED") return 3;
  if (status === "TRAINING_IN_PROGRESS") return 4;
  if (status === "CERTIFIED") return 5;
  return -1;
}

export function ApplicationStatusBadge({ status }: { status: string }) {
  const meta = APPLICATION_STATUS_META[status] ?? { label: status, tone: "neutral" as const };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function ApplicationTracker({ application }: { application: ApplicationDetail }) {
  const currentIdx = stageIndex(application.status);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title={`Application ${application.reference_code}`}
          description={`Last updated ${formatDateTime(application.updated_at)}`}
          action={<ApplicationStatusBadge status={application.status} />}
        />
        <div className="space-y-5 px-5 py-5">
          {currentIdx >= 0 ? (
            <ol className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {STAGES.map((stage, idx) => {
                const done = idx < currentIdx || (idx === currentIdx && application.status === "CERTIFIED");
                const current = idx === currentIdx && application.status !== "CERTIFIED";
                return (
                  <li
                    key={stage.key}
                    className={clsx(
                      "rounded-lg border px-3 py-2.5 text-xs",
                      done
                        ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                        : current
                          ? "border-brand-300 bg-brand-50 text-brand-900"
                          : "border-slate-200 bg-slate-50 text-slate-500",
                    )}
                  >
                    <div className="flex items-center gap-1.5 font-semibold">
                      {done ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" /> : <Clock className="h-3.5 w-3.5" />}
                      {stage.label}
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="text-sm text-slate-600">
              Current lifecycle status: <strong>{APPLICATION_STATUS_META[application.status]?.label ?? application.status}</strong>.
            </p>
          )}

          <div className="grid gap-4 rounded-lg border border-slate-100 bg-slate-50 p-4 text-sm sm:grid-cols-3">
            <div>
              <p className="text-xs text-slate-500">Submitted at</p>
              <p className="mt-0.5 font-medium text-slate-900">{formatDateTime(application.submitted_at)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Documents uploaded</p>
              <p className="mt-0.5 font-medium text-slate-900">
                {application.completeness.uploaded_document_count} / {application.completeness.required_document_count}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Operational region</p>
              <p className="mt-0.5 font-medium text-slate-900">{application.region ?? "Pending address"}</p>
            </div>
          </div>

          {application.status === "SUBMITTED" && (
            <p className="text-sm text-slate-600">
              Your application and uploaded documents are securely stored in PostgreSQL and private object storage.
              Automated document extraction, rules evaluation, and reviewer decisions run in the upcoming review pipeline phases.
            </p>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Application history" description="Complete chronological log of application saves, document uploads, and status transitions." />
        {application.events.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-500">No events recorded yet.</p>
        ) : (
          <ol className="divide-y divide-slate-100">
            {application.events.map((ev) => (
              <li key={ev.id} className="flex flex-wrap items-start justify-between gap-2 px-5 py-3.5 text-sm">
                <div>
                  <p className="font-medium text-slate-900">{ev.summary}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    <span className="font-mono">{ev.event_type}</span>
                    {ev.from_status && ev.to_status && ev.from_status !== ev.to_status
                      ? ` · ${ev.from_status} → ${ev.to_status}`
                      : ""}
                    {ev.actor_role ? ` · ${ev.actor_role}` : ""}
                  </p>
                </div>
                <span className="text-xs text-slate-500">{formatDateTime(ev.created_at)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
