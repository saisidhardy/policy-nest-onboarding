"use client";

import {
  Award,
  CheckCircle2,
  Clock,
  ExternalLink,
  GraduationCap,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { TrainingRecord } from "@/lib/types";

interface TrainingStatusPanelProps {
  applicationId: string;
  canSync?: boolean;
  onApplicationStatusChanged?: () => void;
}

export function TrainingStatusPanel({
  applicationId,
  canSync = true,
  onApplicationStatusChanged,
}: TrainingStatusPanelProps) {
  const [training, setTraining] = useState<TrainingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api<TrainingRecord>(`/applications/${applicationId}/training`);
      setTraining(res);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load training status.");
    }
  }, [applicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runEnroll() {
    setBusyAction("enroll");
    setError(null);
    try {
      const res = await api<TrainingRecord>(`/applications/${applicationId}/training/enroll`, { method: "POST" });
      setTraining(res);
      onApplicationStatusChanged?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Enrollment request failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function runSync(sandboxAction?: string) {
    setBusyAction(sandboxAction || "sync");
    setError(null);
    try {
      const res = await api<TrainingRecord>(`/applications/${applicationId}/training/sync`, {
        method: "POST",
        body: sandboxAction ? { sandbox_action: sandboxAction } : {},
      });
      setTraining(res);
      onApplicationStatusChanged?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "LMS status sync failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function runRetry() {
    setBusyAction("retry");
    setError(null);
    try {
      const res = await api<TrainingRecord>(`/applications/${applicationId}/training/retry`, { method: "POST" });
      setTraining(res);
      onApplicationStatusChanged?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Retry failed.");
    } finally {
      setBusyAction(null);
    }
  }

  if (!training && !error) return <Spinner label="Loading LMS training status" />;
  if (!training && error) return <Alert tone="error">{error}</Alert>;
  if (!training) return null;

  const eligible = training.eligibility_status === "ELIGIBLE";
  const adapter = training.adapter_status;
  const hasSyncIssue =
    training.sync_status === "RETRY_PENDING" ||
    training.sync_status === "ERROR" ||
    training.sync_status === "NOT_CONFIGURED";

  return (
    <Card>
      <CardHeader
        title="IRDAI 15-Hour POSP Training & Certification"
        description="Synchronized with external Learning Management System (LMS) with deterministic 15-hour & exam guards."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {training.is_simulated && <Badge tone="warning">SANDBOX · Simulated</Badge>}
            {adapter.mode === "LIVE" && <Badge tone="success">LMS Live</Badge>}
            {adapter.status === "NOT_CONFIGURED" && <Badge tone="neutral">LMS Not Configured</Badge>}
            {training.certification_status === "CERTIFIED" ? (
              <Badge tone="success">Certified POSP</Badge>
            ) : eligible ? (
              <Badge tone="brand">{training.enrollment_status.replaceAll("_", " ")}</Badge>
            ) : (
              <Badge tone="neutral">Not Eligible Yet</Badge>
            )}
          </div>
        }
      />

      <div className="space-y-5 p-5">
        {error && <Alert tone="error">{error}</Alert>}

        {adapter.status !== "CONFIGURED" ? (
          <Alert tone="warning" title="External LMS Adapter Configuration Status">
            {adapter.detail}
          </Alert>
        ) : (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs text-slate-600">
            <strong className="text-slate-800">Adapter:</strong> {adapter.detail}
            {adapter.webhook_configured && " Inbound HMAC webhook listener enabled."}
          </div>
        )}

        {hasSyncIssue && training.last_error_message && (
          <Alert tone="error" title={`LMS Sync ${training.sync_status.replaceAll("_", " ")} (${training.last_error_code ?? "ERROR"})`}>
            <p>{training.last_error_message}</p>
            <p className="mt-1 text-xs">
              Attempts: {training.sync_attempts} / {training.max_sync_attempts}
              {training.next_retry_at ? ` · Next scheduled retry: ${formatDateTime(training.next_retry_at)}` : ""}
            </p>
          </Alert>
        )}

        {!eligible ? (
          <Alert tone="info" title="Training Eligibility Check">
            {training.eligibility_reason || "KYC approval is required before LMS enrollment."}
          </Alert>
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                  <span>15-Hour Curriculum Progress</span>
                  <GraduationCap className="h-4 w-4 text-brand-700" />
                </div>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {training.completed_hours.toFixed(1)} / {training.required_hours.toFixed(1)} hrs
                </p>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-brand-700 transition-all"
                    style={{ width: `${Math.min(100, training.progress_pct)}%` }}
                  />
                </div>
                <p className="mt-1.5 text-xs text-slate-500">
                  {training.progress_pct.toFixed(0)}% complete · {training.enrollment_status.replaceAll("_", " ")}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                  <span>Proctored POSP Examination</span>
                  <Clock className="h-4 w-4 text-slate-500" />
                </div>
                <p className="mt-2 text-lg font-semibold text-slate-900">{training.exam_status.replaceAll("_", " ")}</p>
                <p className="mt-1 text-xs text-slate-600">
                  Score: {training.exam_score_pct !== null ? `${training.exam_score_pct.toFixed(1)}% (min 50%)` : "—"} · Attempts:{" "}
                  {training.exam_attempts}
                </p>
                {training.next_exam_eligible_at && (
                  <p className="mt-1 text-xs font-medium text-amber-700">
                    24h retake cooldown until {formatDateTime(training.next_exam_eligible_at)}
                  </p>
                )}
              </div>

              <div className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                  <span>POSP Certificate Status</span>
                  <Award className="h-4 w-4 text-emerald-700" />
                </div>
                <p className="mt-2 text-lg font-semibold text-slate-900">
                  {training.certification_status.replaceAll("_", " ")}
                </p>
                {training.certificate_number ? (
                  <>
                    <p className="mt-1 font-mono text-xs font-semibold text-emerald-800">{training.certificate_number}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Issued {formatDateTime(training.certified_at)} · Valid until {formatDateTime(training.certificate_valid_until)}
                    </p>
                  </>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">
                    Issued upon 15.0h curriculum completion and exam pass (&ge;50%).
                  </p>
                )}
              </div>
            </div>

            {canSync && (
              <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
                {training.enrollment_status === "NOT_ENROLLED" && (
                  <Button onClick={runEnroll} loading={busyAction === "enroll"}>
                    Enroll in LMS Training
                  </Button>
                )}
                {training.external_enrollment_id && (
                  <Button variant="secondary" onClick={() => runSync()} loading={busyAction === "sync"}>
                    <RefreshCw className="h-4 w-4" /> Sync LMS Status
                  </Button>
                )}
                {hasSyncIssue && (
                  <Button variant="secondary" onClick={runRetry} loading={busyAction === "retry"}>
                    <RotateCcw className="h-4 w-4" /> Retry Failed Sync
                  </Button>
                )}
                {training.lms_launch_url && training.lms_launch_url.startsWith("http") && (
                  <a
                    href={training.lms_launch_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-10 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Launch LMS Portal <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>
            )}

            {canSync && adapter.mode === "SANDBOX" && (
              <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
                  Non-Production Sandbox Controls (Simulated LMS Events)
                </p>
                <p className="mt-0.5 text-xs text-amber-800">
                  Available only when LMS_PROVIDER=sandbox in non-production environments to verify sync, cooldown, retry, and certification workflows.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" loading={busyAction === "ADVANCE_7_5H"} onClick={() => runSync("ADVANCE_7_5H")}>
                    Log 7.5h Progress
                  </Button>
                  <Button size="sm" variant="secondary" loading={busyAction === "COMPLETE_15H"} onClick={() => runSync("COMPLETE_15H")}>
                    Complete 15.0h Curriculum
                  </Button>
                  <Button size="sm" variant="secondary" loading={busyAction === "FAIL_EXAM"} onClick={() => runSync("FAIL_EXAM")}>
                    Simulate Exam Fail (Cooldown)
                  </Button>
                  <Button size="sm" variant="secondary" loading={busyAction === "SIMULATE_SYNC_ERROR"} onClick={() => runSync("SIMULATE_SYNC_ERROR")}>
                    Simulate HTTP 503 Error
                  </Button>
                  <Button size="sm" loading={busyAction === "PASS_EXAM"} onClick={() => runSync("PASS_EXAM")}>
                    Pass Exam &amp; Certify
                  </Button>
                </div>
              </div>
            )}

            <div>
              <h4 className="mb-2 text-sm font-semibold text-slate-900">Mandatory IRDAI POSP Curriculum Modules</h4>
              <div className="grid gap-2 sm:grid-cols-2">
                {training.module_progress.map((mod) => (
                  <div
                    key={mod.code}
                    className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs"
                  >
                    <div className="flex items-center gap-2">
                      {mod.completed ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                      ) : (
                        <Clock className="h-4 w-4 shrink-0 text-slate-400" />
                      )}
                      <div>
                        <p className="font-medium text-slate-900">{mod.code} · {mod.title}</p>
                        <p className="text-slate-500">
                          {mod.logged_hours.toFixed(1)} / {mod.required_hours.toFixed(1)} hrs logged
                        </p>
                      </div>
                    </div>
                    <Badge tone={mod.completed ? "success" : "neutral"}>{mod.completed ? "Done" : "Pending"}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {training.sync_logs.length > 0 && (
          <div>
            <h4 className="mb-2 text-sm font-semibold text-slate-900">LMS Synchronization Log</h4>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Timestamp</th>
                    <th className="px-3 py-2">Operation</th>
                    <th className="px-3 py-2">Origin</th>
                    <th className="px-3 py-2">Outcome</th>
                    <th className="px-3 py-2">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {training.sync_logs.slice(0, 6).map((log) => (
                    <tr key={log.id}>
                      <td className="px-3 py-2 text-slate-500">{formatDateTime(log.occurred_at)}</td>
                      <td className="px-3 py-2 font-medium text-slate-800">{log.operation} (#{log.attempt_number})</td>
                      <td className="px-3 py-2 text-slate-600">
                        {log.adapter_origin}
                        {log.is_simulated ? " (Simulated)" : ""}
                      </td>
                      <td className="px-3 py-2">
                        <Badge tone={log.outcome === "SUCCESS" ? "success" : log.outcome === "RETRY_SCHEDULED" ? "warning" : "danger"}>
                          {log.outcome}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-slate-600">{log.error_message || `HTTP ${log.http_status ?? 200}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
