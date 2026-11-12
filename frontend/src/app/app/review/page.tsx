"use client";

import clsx from "clsx";
import { AlertOctagon, FileCheck2, Search, ShieldAlert, UserCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { ReviewPortalTabs } from "@/components/review/ReviewPortalTabs";
import { Alert, Badge, Button, Card, Input, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { ReviewQueueItem, ReviewQueuePage } from "@/lib/types";

type QueueView = "pending" | "assigned_to_me" | "unassigned" | "escalated" | "fraud" | "open_appeals" | "all";

export default function ReviewerQueuePage() {
  return (
    <RequirePermission permission="application:review">
      <ReviewerQueueInner />
    </RequirePermission>
  );
}

function ReviewerQueueInner() {
  const { me, can } = useAuth();
  const [data, setData] = useState<ReviewQueuePage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [queueView, setQueueView] = useState<QueueView>("pending");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [outcomeFilter, setOutcomeFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("urgency");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    try {
      const res = await api<ReviewQueuePage>("/review/queue", {
        query: {
          queue_view: queueView,
          q: search.trim() || undefined,
          status: statusFilter !== "ALL" ? statusFilter : undefined,
          outcome: outcomeFilter !== "ALL" ? outcomeFilter : undefined,
          sort_by: sortBy,
          page,
          page_size: 20,
        },
      });
      setData(res);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load review queue.");
    }
  }, [queueView, search, statusFilter, outcomeFilter, sortBy, page]);

  useEffect(() => {
    void load();
  }, [load]);

  async function quickClaim(app: ReviewQueueItem) {
    setBusyId(app.id);
    setError(null);
    try {
      const release = app.assigned_reviewer_id === me?.user.id;
      await api(`/review/applications/${app.id}/claim`, {
        method: "POST",
        body: { action: release ? "release" : "claim" },
      });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update assignment.");
    } finally {
      setBusyId(null);
    }
  }

  const kpis = data?.kpis;

  const views: { key: QueueView; label: string; count?: number; show?: boolean }[] = [
    { key: "pending", label: "Pending Queue", count: kpis?.pending_review_count, show: true },
    { key: "assigned_to_me", label: "Assigned to Me", count: kpis?.assigned_to_me_count, show: true },
    { key: "unassigned", label: "Unassigned", count: kpis?.unassigned_pending_count, show: true },
    { key: "escalated", label: "Escalated", count: kpis?.escalated_count, show: true },
    { key: "fraud", label: "Fraud Desk", count: kpis?.fraud_flagged_count, show: can("fraud:review") || (kpis?.fraud_flagged_count ?? 0) > 0 },
    { key: "open_appeals", label: "Open Appeals", count: kpis?.open_appeals_count, show: true },
    { key: "all", label: "All Records", show: true },
  ];

  return (
    <div>
      <PageHeader
        title="Reviewer & Operations Portal"
        description="Manage regional onboarding queues, verify extracted KYC records, investigate escalations and fraud alerts, and record auditable decisions."
      />
      <ReviewPortalTabs />

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      {kpis && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiBox label="Pending Review" value={kpis.pending_review_count} hint={`${kpis.unassigned_pending_count} unassigned`} />
          <KpiBox label="In Review" value={kpis.in_review_count} hint={`${kpis.assigned_to_me_count} assigned to you`} />
          <KpiBox label="Escalated / Fraud" value={kpis.escalated_count + kpis.fraud_flagged_count} hint={`${kpis.fraud_flagged_count} fraud flagged`} highlight={kpis.fraud_flagged_count > 0} />
          <KpiBox label="Open Appeals" value={kpis.open_appeals_count} hint="Awaiting Senior Reviewer" />
          <KpiBox label="KYC Approved" value={kpis.kyc_approved_count} hint={`${kpis.rejected_count} rejected`} />
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {views
          .filter((v) => v.show)
          .map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => {
                setQueueView(v.key);
                setPage(1);
              }}
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                queueView === v.key
                  ? "border-brand-700 bg-brand-700 text-white"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
              )}
            >
              {v.label}
              {v.count !== undefined && (
                <span
                  className={clsx(
                    "rounded-full px-1.5 py-0.5 text-[11px]",
                    queueView === v.key ? "bg-white/20 text-white" : "bg-slate-100 text-slate-700",
                  )}
                >
                  {v.count}
                </span>
              )}
            </button>
          ))}
      </div>

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative flex-1 lg:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              aria-label="Search review queue"
              placeholder="Search APP ref, applicant, city, state, last 4..."
              className="pl-9"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filter by application status"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800"
            >
              <option value="ALL">All statuses</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="REWORK_SUBMITTED">Rework submitted</option>
              <option value="IN_REVIEW">In review</option>
              <option value="NEEDS_MORE_INFO">Needs more info</option>
              <option value="KYC_APPROVED">KYC approved</option>
              <option value="REJECTED">Rejected</option>
              <option value="DRAFT">Draft</option>
            </select>
            <select
              aria-label="Filter by rule outcome"
              value={outcomeFilter}
              onChange={(e) => {
                setOutcomeFilter(e.target.value);
                setPage(1);
              }}
              className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800"
            >
              <option value="ALL">All rule outcomes</option>
              <option value="HUMAN_REVIEW">Human Review</option>
              <option value="NEEDS_MORE_INFO">Needs More Info</option>
              <option value="REJECT_RECOMMENDED">Reject Recommended</option>
              <option value="AUTO_PASS_ELIGIBLE">Auto-Pass Eligible</option>
            </select>
            <select
              aria-label="Sort queue"
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800"
            >
              <option value="urgency">Sort: Urgency &amp; SLA</option>
              <option value="oldest_submitted">Sort: Oldest first</option>
              <option value="newest_submitted">Sort: Newest first</option>
            </select>
          </div>
        </div>

        {!data ? (
          <div className="p-6">
            <Spinner label="Loading regional review queue" />
          </div>
        ) : data.items.length === 0 ? (
          <div className="px-6 py-10 text-center text-sm text-slate-600">
            <FileCheck2 className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-2 font-medium text-slate-800">No applications match this queue view</p>
            <p className="mt-1 text-xs text-slate-500">Only applications within your authorized region and clearance level appear here.</p>
          </div>
        ) : (
          <>
            <div className="divide-y divide-slate-200">
              {data.items.map((app) => {
                const isMine = app.assigned_reviewer_id === me?.user.id;
                const canClaim = app.status !== "DRAFT" && app.status !== "WITHDRAWN";
                return (
                  <div key={app.id} className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-semibold text-slate-900">{app.reference_code}</span>
                        <ApplicationStatusBadge status={app.status} />
                        {app.region && <Badge tone="neutral">{app.region}</Badge>}
                        {app.latest_outcome && <Badge tone="brand">{app.latest_outcome}</Badge>}
                        {app.fraud_flag && (
                          <Badge tone="danger">
                            <AlertOctagon className="mr-1 h-3 w-3" /> FRAUD DESK
                          </Badge>
                        )}
                        {app.escalated_at && !app.fraud_flag && (
                          <Badge tone="warning">
                            <ShieldAlert className="mr-1 h-3 w-3" /> Escalated
                          </Badge>
                        )}
                        {app.open_appeal_count > 0 && <Badge tone="warning">Open Appeal</Badge>}
                        {app.assigned_reviewer_name && (
                          <Badge tone={isMine ? "success" : "neutral"}>
                            <UserCheck className="mr-1 h-3 w-3" />
                            {isMine ? "Assigned to you" : app.assigned_reviewer_name}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm font-medium text-slate-800">
                        {app.full_name || "Draft applicant"}
                        {(app.city || app.state) && (
                          <span className="ml-2 font-normal text-slate-500">
                            · {[app.city, app.state].filter(Boolean).join(", ")}
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-slate-500">
                        {app.uploaded_document_count}/{app.required_document_count} docs · Reworks: {app.rework_count} ·{" "}
                        {app.submitted_at
                          ? `Submitted ${formatDateTime(app.submitted_at)}`
                          : `Saved ${formatDateTime(app.last_saved_at)}`}
                        {app.latest_reason_codes.length > 0 && ` · Codes: ${app.latest_reason_codes.join(", ")}`}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {canClaim && (
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={busyId === app.id}
                          onClick={() => void quickClaim(app)}
                        >
                          {isMine ? "Release" : "Claim"}
                        </Button>
                      )}
                      <Link
                        href={`/app/review/${app.id}`}
                        className="inline-flex h-8 items-center justify-center rounded-lg bg-brand-700 px-3.5 text-sm font-medium text-white hover:bg-brand-800"
                      >
                        Open workspace
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>

            {data.total > data.page_size && (
              <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3 text-xs text-slate-600">
                <span>
                  Showing {(data.page - 1) * data.page_size + 1}–{Math.min(data.page * data.page_size, data.total)} of{" "}
                  {data.total}
                </span>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled={data.page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={data.page * data.page_size >= data.total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

function KpiBox({
  label,
  value,
  hint,
  highlight = false,
}: {
  label: string;
  value: number;
  hint: string;
  highlight?: boolean;
}) {
  return (
    <Card className={highlight ? "border-red-300 bg-red-50/40 p-4" : "p-4"}>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{hint}</p>
    </Card>
  );
}
