"use client";

import { Search, UserPlus } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { RequirePermission } from "@/components/RequirePermission";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AdminApplicationItem, AdminApplicationPage, ReviewerWorkload } from "@/lib/types";

export default function AdminApplicationsPage() {
  return (
    <RequirePermission permission="config:manage">
      <Suspense>
        <AdminApplicationsView />
      </Suspense>
    </RequirePermission>
  );
}

const STATUS_OPTIONS = [
  "",
  "DRAFT",
  "SUBMITTED",
  "IN_REVIEW",
  "NEEDS_MORE_INFO",
  "REWORK_SUBMITTED",
  "KYC_APPROVED",
  "TRAINING_IN_PROGRESS",
  "CERTIFIED",
  "REJECTED",
  "WITHDRAWN",
];

function AdminApplicationsView() {
  const sp = useSearchParams();
  const [data, setData] = useState<AdminApplicationPage | null>(null);
  const [reviewers, setReviewers] = useState<ReviewerWorkload[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState(sp.get("status") ?? "");
  const [escalatedOnly, setEscalatedOnly] = useState(sp.get("escalated") === "1");
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [assignApp, setAssignApp] = useState<AdminApplicationItem | null>(null);
  const [assignReviewerId, setAssignReviewerId] = useState("");
  const [assignReason, setAssignReason] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (q.trim()) params.set("q", q.trim());
    if (status) params.set("status", status);
    if (escalatedOnly) params.set("escalated_only", "true");
    if (unassignedOnly) params.set("unassigned_only", "true");
    try {
      const [apps, revs] = await Promise.all([
        api<AdminApplicationPage>(`/admin/applications?${params.toString()}`),
        api<ReviewerWorkload[]>("/admin/reviewers"),
      ]);
      setData(apps);
      setReviewers(revs.filter((r) => r.is_active));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load applications.");
    } finally {
      setLoading(false);
    }
  }, [q, status, escalatedOnly, unassignedOnly, page]);

  useEffect(() => {
    void load();
  }, [load]);

  function openAssign(item: AdminApplicationItem) {
    setAssignApp(item);
    setAssignReviewerId(item.assigned_reviewer_id ?? "");
    setAssignReason("");
    setAssignError(null);
  }

  async function submitAssign(e: React.FormEvent) {
    e.preventDefault();
    if (!assignApp) return;
    setAssigning(true);
    setAssignError(null);
    try {
      const updated = await api<AdminApplicationItem>(`/admin/applications/${assignApp.id}/assign`, {
        method: "POST",
        body: JSON.stringify({
          reviewer_id: assignReviewerId || null,
          reason: assignReason,
        }),
      });
      setNotice(
        updated.assigned_reviewer_name
          ? `Assigned ${updated.reference_code} to ${updated.assigned_reviewer_name}.`
          : `Cleared reviewer assignment for ${updated.reference_code}.`,
      );
      setAssignApp(null);
      await load();
    } catch (e) {
      setAssignError(e instanceof ApiError ? e.message : "Failed to assign reviewer.");
    } finally {
      setAssigning(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Application management"
        description="Global pipeline oversight and audited reviewer assignment. Separation of Duties keeps KYC approval and rejection exclusively with Reviewer and Senior Reviewer roles."
      />

      {notice && (
        <Alert tone="success" className="mb-4">
          {notice}
        </Alert>
      )}
      {error && (
        <Alert tone="error" className="mb-4">
          {error}
        </Alert>
      )}

      {data && Object.keys(data.counts_by_status).length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setStatus("");
              setPage(1);
            }}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              !status ? "border-brand-600 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            All ({Object.values(data.counts_by_status).reduce((a, b) => a + b, 0)})
          </button>
          {Object.entries(data.counts_by_status).map(([st, count]) => (
            <button
              key={st}
              type="button"
              onClick={() => {
                setStatus(st);
                setPage(1);
              }}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                status === st ? "border-brand-600 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600"
              }`}
            >
              {st.replaceAll("_", " ")} ({count})
            </button>
          ))}
        </div>
      )}

      <Card>
        <CardHeader
          title="Applications directory"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  aria-label="Search applications"
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setPage(1);
                  }}
                  placeholder="Reference, name, or email"
                  className="w-56 pl-9"
                />
              </div>
              <Select
                aria-label="Status filter"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
                className="w-44"
              >
                {STATUS_OPTIONS.map((st) => (
                  <option key={st || "all"} value={st}>
                    {st ? st.replaceAll("_", " ") : "All statuses"}
                  </option>
                ))}
              </Select>
              <label className="flex items-center gap-1.5 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={escalatedOnly}
                  onChange={(e) => {
                    setEscalatedOnly(e.target.checked);
                    setPage(1);
                  }}
                />
                Escalated
              </label>
              <label className="flex items-center gap-1.5 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={unassignedOnly}
                  onChange={(e) => {
                    setUnassignedOnly(e.target.checked);
                    setPage(1);
                  }}
                />
                Unassigned
              </label>
            </div>
          }
        />

        {loading || !data ? (
          <div className="p-8">
            <Spinner label="Loading applications" />
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState title="No applications match the current filters" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-100 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-5 py-3 text-left font-medium">Reference &amp; applicant</th>
                    <th className="px-3 py-3 text-left font-medium">Region</th>
                    <th className="px-3 py-3 text-left font-medium">Status</th>
                    <th className="px-3 py-3 text-left font-medium">Assigned reviewer</th>
                    <th className="px-3 py-3 text-left font-medium">Training</th>
                    <th className="px-3 py-3 text-left font-medium">Updated</th>
                    <th className="px-5 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/70">
                      <td className="px-5 py-3.5">
                        <p className="font-mono text-xs font-semibold text-slate-900">{item.reference_code}</p>
                        <p className="font-medium text-slate-900">{item.applicant_name}</p>
                        <p className="text-xs text-slate-500">{item.applicant_email}</p>
                      </td>
                      <td className="px-3 py-3.5 text-slate-700">{item.region ?? "—"}</td>
                      <td className="px-3 py-3.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <ApplicationStatusBadge status={item.status} />
                          {item.is_escalated && <Badge tone="warning">Escalated</Badge>}
                          {item.fraud_flag && <Badge tone="danger">Fraud flag</Badge>}
                        </div>
                      </td>
                      <td className="px-3 py-3.5">
                        {item.assigned_reviewer_name ? (
                          <div>
                            <p className="font-medium text-slate-800">{item.assigned_reviewer_name}</p>
                            <p className="text-xs text-slate-500">{item.assigned_reviewer_email}</p>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">Unassigned</span>
                        )}
                      </td>
                      <td className="px-3 py-3.5">
                        {item.training_status ? (
                          <Badge tone={item.training_status === "CERTIFIED" ? "success" : "neutral"}>
                            {item.training_status.replaceAll("_", " ")}
                          </Badge>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3.5 text-xs text-slate-600">{formatDateTime(item.updated_at)}</td>
                      <td className="px-5 py-3.5 text-right">
                        <Button variant="secondary" size="sm" onClick={() => openAssign(item)}>
                          <UserPlus className="h-3.5 w-3.5" /> Assign
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>

      <Dialog
        open={Boolean(assignApp)}
        onClose={() => setAssignApp(null)}
        title={`Assign reviewer — ${assignApp?.reference_code ?? ""}`}
        description={
          assignApp?.is_escalated
            ? "Escalated application: must be assigned to an active Senior Reviewer."
            : "Select an active Reviewer or Senior Reviewer, or clear assignment."
        }
      >
        <form className="space-y-4" onSubmit={submitAssign}>
          {assignError && <Alert tone="error">{assignError}</Alert>}
          <Field label="Reviewer" htmlFor="app-assign-reviewer">
            <Select id="app-assign-reviewer" value={assignReviewerId} onChange={(e) => setAssignReviewerId(e.target.value)}>
              <option value="">Unassigned</option>
              {reviewers.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.full_name} ({r.role === "SENIOR_REVIEWER" ? "Senior" : "Reviewer"} · {r.region ?? "No region"} · {r.active_assigned_count} active)
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Assignment reason" htmlFor="app-assign-reason" hint="Minimum 5 characters; logged in the audit trail.">
            <Input
              id="app-assign-reason"
              required
              minLength={5}
              value={assignReason}
              onChange={(e) => setAssignReason(e.target.value)}
              placeholder="e.g., Routing escalated KYC review"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setAssignApp(null)}>
              Cancel
            </Button>
            <Button type="submit" loading={assigning}>
              Save assignment
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
