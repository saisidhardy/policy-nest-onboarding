"use client";

import { RefreshCw, RotateCcw, ScrollText, Search } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { TrainingStatusPanel } from "@/components/training/TrainingStatusPanel";
import { Alert, Badge, Button, Card, Input, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { ApplicationDetail, BatchRetryOut, TrainingOverview } from "@/lib/types";

export default function TrainingPortalPage() {
  return (
    <RequirePermission permission="profile:read">
      <TrainingPortalInner />
    </RequirePermission>
  );
}

function TrainingPortalInner() {
  const { me, can } = useAuth();
  if (!me) return null;

  if (can("application:review") || can("system:read")) {
    return <OpsTrainingMonitor />;
  }
  return <ApplicantTrainingView />;
}

function ApplicantTrainingView() {
  const [app, setApp] = useState<ApplicationDetail | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const loadApp = useCallback(async () => {
    try {
      const current = await api<ApplicationDetail | null>("/applications/current");
      setApp(current);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load onboarding application.");
      setApp(null);
    }
  }, []);

  useEffect(() => {
    void loadApp();
  }, [loadApp]);

  if (app === undefined) return <Spinner label="Checking POSP training eligibility" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="POSP Training & Certification"
        description="Complete your mandatory 15-hour IRDAI POSP curriculum and examination via PolicyNest's synchronized LMS."
      />
      {error && <Alert tone="error">{error}</Alert>}
      {!app ? (
        <Alert tone="info" title="No active onboarding application found">
          Start and submit your POSP onboarding application first. Training unlocks automatically after KYC approval.{" "}
          <Link href="/app/onboarding" className="font-semibold underline">
            Go to onboarding
          </Link>
        </Alert>
      ) : (
        <>
          {(app.status === "CERTIFIED" || app.status === "KYC_APPROVED") && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-300 bg-emerald-50/70 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white font-bold text-sm">
                  ✓
                </div>
                <div>
                  <p className="font-semibold text-emerald-950">
                    {app.status === "CERTIFIED"
                      ? "IRDAI POSP Appointment Certified"
                      : "KYC Approved · Training In Progress"}
                  </p>
                  <p className="text-xs text-emerald-800">
                    {app.status === "CERTIFIED"
                      ? "Your statutory 15-hour training and examination are completed. You can view or print your official compliance dossier."
                      : "Your onboarding verification is passed. Complete your 15-hour training curriculum below to finalize appointment."}
                  </p>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => window.open(`/api/v1/applications/${app.id}/dossier?format=html`, "_blank")}
              >
                <ScrollText className="h-4 w-4 mr-1.5" /> View Official Dossier
              </Button>
            </div>
          )}
          <TrainingStatusPanel applicationId={app.id} onApplicationStatusChanged={loadApp} />
        </>
      )}
    </div>
  );
}

function OpsTrainingMonitor() {
  const [overview, setOverview] = useState<TrainingOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [syncFilter, setSyncFilter] = useState("ALL");
  const [page, setPage] = useState(1);
  const [retryingAll, setRetryingAll] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api<TrainingOverview>("/training/overview", {
        query: {
          q: search.trim() || undefined,
          sync_status: syncFilter !== "ALL" ? syncFilter : undefined,
          page,
          page_size: 20,
        },
      });
      setOverview(res);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load LMS training overview.");
    }
  }, [search, syncFilter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  async function retryDue() {
    setRetryingAll(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api<BatchRetryOut>("/training/retry-due", { method: "POST" });
      setNotice(res.message);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Batch retry failed.");
    } finally {
      setRetryingAll(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="LMS Training & Certification Operations"
        description="Monitor KYC-approved candidates across 15-hour training, exams, POSP certificates, and LMS sync retries."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => void load()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={retryDue} loading={retryingAll}>
              <RotateCcw className="h-4 w-4" /> Retry Failed / Due Syncs
            </Button>
          </div>
        }
      />

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="info">{notice}</Alert>}

      {overview && (
        <>
          <Alert
            tone={overview.adapter_status.status === "CONFIGURED" ? "info" : "warning"}
            title={`LMS Integration Adapter · ${overview.adapter_status.status} (${overview.adapter_status.mode})`}
          >
            {overview.adapter_status.detail}
          </Alert>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <StatTile label="KYC Approved Awaiting LMS" value={overview.kyc_approved_awaiting_training} />
            <StatTile label="Training In Progress" value={overview.training_in_progress_count} />
            <StatTile label="15h Complete · Awaiting Exam" value={overview.training_completed_awaiting_exam} />
            <StatTile label="Certified POSPs" value={overview.certified_count} tone="text-emerald-700" />
            <StatTile label="Sync Retry Pending" value={overview.sync_retry_pending_count} tone="text-amber-700" />
            <StatTile label="Sync Errors / Unconfigured" value={overview.sync_error_count} tone="text-rose-700" />
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4">
              <div className="relative w-full max-w-xs">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                  placeholder="Search APP ref, applicant, or certificate..."
                  className="pl-9"
                />
              </div>
              <select
                value={syncFilter}
                onChange={(e) => {
                  setSyncFilter(e.target.value);
                  setPage(1);
                }}
                aria-label="Filter by sync status"
                className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900"
              >
                <option value="ALL">All sync statuses</option>
                <option value="IDLE">Idle</option>
                <option value="SYNCED">Synced</option>
                <option value="RETRY_PENDING">Retry pending</option>
                <option value="ERROR">Sync error</option>
                <option value="NOT_CONFIGURED">Not configured</option>
              </select>
            </div>

            {overview.items.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No KYC-approved or training applications match your current filter.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                  <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Applicant</th>
                      <th className="px-4 py-3">App Status</th>
                      <th className="px-4 py-3">15h Progress</th>
                      <th className="px-4 py-3">Exam &amp; Certificate</th>
                      <th className="px-4 py-3">Sync Status</th>
                      <th className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {overview.items.map((item) => (
                      <tr key={item.application_id} className="hover:bg-slate-50/70">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-slate-900">{item.reference_code}</p>
                          <p className="text-xs text-slate-500">
                            {item.applicant_name || "Unnamed"} · {item.region || "—"}
                          </p>
                        </td>
                        <td className="px-4 py-3">
                          <ApplicationStatusBadge status={item.application_status} />
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-700">
                          <p className="font-medium">
                            {item.completed_hours.toFixed(1)} / {item.required_hours.toFixed(1)} hrs ({item.progress_pct.toFixed(0)}%)
                          </p>
                          <p className="text-slate-500">{item.enrollment_status.replaceAll("_", " ")}</p>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <p className="font-medium text-slate-800">{item.exam_status.replaceAll("_", " ")}</p>
                          <p className="text-slate-500">
                            {item.certificate_number ? (
                              <span className="font-mono text-emerald-700">{item.certificate_number}</span>
                            ) : (
                              "Not certified"
                            )}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <div className="flex flex-wrap items-center gap-1">
                            <Badge
                              tone={
                                item.sync_status === "SYNCED"
                                  ? "success"
                                  : item.sync_status === "RETRY_PENDING"
                                    ? "warning"
                                    : item.sync_status === "IDLE"
                                      ? "neutral"
                                      : "danger"
                              }
                            >
                              {item.sync_status}
                            </Badge>
                            {item.is_simulated && <Badge tone="warning">Sandbox</Badge>}
                          </div>
                          {item.last_error_code && (
                            <p className="mt-1 text-[11px] text-rose-700">{item.last_error_code}</p>
                          )}
                          <p className="mt-0.5 text-[11px] text-slate-400">Updated {formatDateTime(item.updated_at)}</p>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            href={`/app/review/${item.application_id}`}
                            className="inline-flex h-8 items-center rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                          >
                            Inspect
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function StatTile({ label, value, tone = "text-slate-900" }: { label: string; value: number; tone?: string }) {
  return (
    <Card className="p-3.5">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p>
    </Card>
  );
}
