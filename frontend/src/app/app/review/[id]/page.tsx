"use client";

import { AlertOctagon, ArrowLeft, Eye, ScrollText, ShieldCheck, UserCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { DocumentPreviewModal } from "@/components/onboarding/DocumentPreviewModal";
import { FieldComparisonCard } from "@/components/review/FieldComparisonCard";
import { TrainingStatusPanel } from "@/components/training/TrainingStatusPanel";
import { DecisionHistoryPanel } from "@/components/verification/DecisionHistoryPanel";
import { VerificationReportPanel } from "@/components/verification/VerificationReportPanel";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type {
  ApplicationDecisionSummary,
  ApplicationDetail,
  ApplicationDocument,
  ApplicationVerificationReport,
  AssignableReviewer,
} from "@/lib/types";

export default function ReviewerDetailPage() {
  return (
    <RequirePermission permission="application:review">
      <ReviewerDetailInner />
    </RequirePermission>
  );
}

function ReviewerDetailInner() {
  const { id } = useParams<{ id: string }>();
  const { me, can } = useAuth();
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [report, setReport] = useState<ApplicationVerificationReport | null>(null);
  const [decisionSummary, setDecisionSummary] = useState<ApplicationDecisionSummary | null>(null);
  const [reviewers, setReviewers] = useState<AssignableReviewer[]>([]);
  const [previewDoc, setPreviewDoc] = useState<ApplicationDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [assignTarget, setAssignTarget] = useState("");
  const [showFraudBox, setShowFraudBox] = useState(false);
  const [fraudReason, setFraudReason] = useState("");
  const [fraudResolveText, setFraudResolveText] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [appData, repData, decData, revList] = await Promise.all([
        api<ApplicationDetail>(`/applications/${id}`),
        api<ApplicationVerificationReport>(`/applications/${id}/verification`),
        api<ApplicationDecisionSummary>(`/applications/${id}/decisions`).catch(() => null),
        api<AssignableReviewer[]>("/review/reviewers").catch(() => []),
      ]);
      setApp(appData);
      setReport(repData);
      setDecisionSummary(decData);
      setReviewers(revList);
      setAssignTarget(appData.assigned_reviewer_id ?? "");
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load application review workspace.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleClaim(action: "claim" | "release" | "assign") {
    if (!app) return;
    setBusy(true);
    setActionNotice(null);
    setError(null);
    try {
      await api<ApplicationDetail>(`/review/applications/${app.id}/claim`, {
        method: "POST",
        body: { action, target_user_id: action === "assign" ? assignTarget || null : null },
      });
      setActionNotice(
        action === "release"
          ? "Application assignment released."
          : action === "assign"
            ? "Application reassigned cleanly."
            : "Application claimed to your active review queue.",
      );
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update assignment.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFraudEscalate(e: React.FormEvent) {
    e.preventDefault();
    if (!app) return;
    setBusy(true);
    setError(null);
    setActionNotice(null);
    try {
      await api<ApplicationDetail>(`/review/applications/${app.id}/fraud-escalate`, {
        method: "POST",
        body: { reason: fraudReason.trim() },
      });
      setFraudReason("");
      setShowFraudBox(false);
      setActionNotice("Escalated application to Fraud Desk.");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to escalate to Fraud Desk.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFraudResolve(resolution: "CLEAR_FLAG" | "CONFIRM_FRAUD_REJECT") {
    if (!app) return;
    setBusy(true);
    setError(null);
    setActionNotice(null);
    try {
      await api<ApplicationDetail>(`/review/applications/${app.id}/fraud-resolve`, {
        method: "POST",
        body: { resolution, reason_text: fraudResolveText.trim() },
      });
      setFraudResolveText("");
      setActionNotice(
        resolution === "CONFIRM_FRAUD_REJECT" ? "Confirmed fraud rejection." : "Cleared fraud flag on application.",
      );
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to resolve fraud escalation.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !app) {
    return (
      <div className="space-y-4">
        <Alert tone="error">{error}</Alert>
        <Link href="/app/review" className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back to queue
        </Link>
      </div>
    );
  }
  if (!app) return <Spinner label="Loading reviewer workspace" />;

  const isMine = app.assigned_reviewer_id === me?.user.id;
  const assignedUser = reviewers.find((r) => r.id === app.assigned_reviewer_id);

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <Link href="/app/review" className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" /> Back to review queue
        </Link>
        <Link href="/app/review/history" className="text-sm font-medium text-brand-700 hover:underline">
          View review history
        </Link>
      </div>

      <PageHeader
        title={`${app.reference_code} · ${app.full_name || "Applicant"}`}
        description={`Submitted ${app.submitted_at ? formatDateTime(app.submitted_at) : "Draft"} · Region: ${app.region ?? "Unassigned"}`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <ApplicationStatusBadge status={app.status} />
            <Badge tone="neutral">Clearance {app.sensitivity}</Badge>
            {app.fraud_flag && (
              <Badge tone="danger">
                <AlertOctagon className="mr-1 h-3 w-3" /> FRAUD FLAGGED
              </Badge>
            )}
            {assignedUser && (
              <Badge tone={isMine ? "success" : "brand"}>
                <UserCheck className="mr-1 h-3 w-3" />
                {isMine ? "Assigned to you" : assignedUser.full_name}
              </Badge>
            )}
          </div>
        }
      />

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}
      {actionNotice && <Alert tone="success" className="mb-4">{actionNotice}</Alert>}

      <div className="space-y-6">
        <Card>
          <CardHeader
            title="Reviewer Assignment & Escalation Controls"
            description="Claim ownership, reassign to a peer (Senior Reviewer), or escalate suspicious records to the Fraud Desk."
          />
          <div className="flex flex-wrap items-end justify-between gap-4 p-5">
            <div className="flex flex-wrap items-center gap-2">
              {app.status !== "DRAFT" && app.status !== "WITHDRAWN" && (
                <Button size="sm" variant="secondary" loading={busy} onClick={() => void handleClaim(isMine ? "release" : "claim")}>
                  {isMine ? "Release assignment" : "Claim for me"}
                </Button>
              )}
              {can("application:escalate") && app.status !== "DRAFT" && app.status !== "WITHDRAWN" && !app.fraud_flag && (
                <Button size="sm" variant="danger" onClick={() => setShowFraudBox((v) => !v)}>
                  <AlertOctagon className="h-3.5 w-3.5" /> Escalate to Fraud Desk
                </Button>
              )}
              {app.status !== "DRAFT" && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => window.open(`/api/v1/applications/${app.id}/dossier?format=html`, "_blank")}
                >
                  <ScrollText className="h-3.5 w-3.5" /> View Dossier
                </Button>
              )}
            </div>

            {can("application:decide_escalated") && reviewers.length > 0 && app.status !== "DRAFT" && (
              <div className="flex items-end gap-2">
                <Field label="Reassign reviewer" htmlFor="assign-reviewer-select">
                  <Select
                    id="assign-reviewer-select"
                    value={assignTarget}
                    onChange={(e) => setAssignTarget(e.target.value)}
                  >
                    <option value="">Select reviewer…</option>
                    {reviewers.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.full_name} ({r.role_code})
                      </option>
                    ))}
                  </Select>
                </Field>
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy}
                  disabled={!assignTarget}
                  onClick={() => void handleClaim("assign")}
                >
                  Assign
                </Button>
              </div>
            )}
          </div>

          {showFraudBox && (
            <form onSubmit={handleFraudEscalate} className="space-y-3 border-t border-slate-200 bg-red-50/40 p-5">
              <Field label="Fraud escalation details" htmlFor="fraud-reason-input">
                <Input
                  id="fraud-reason-input"
                  value={fraudReason}
                  onChange={(e) => setFraudReason(e.target.value)}
                  placeholder="Describe tampered document indicator, synthetic pattern, or identity anomaly (min 10 chars)…"
                  minLength={10}
                  required
                />
              </Field>
              <div className="flex gap-2">
                <Button type="submit" size="sm" variant="danger" loading={busy} disabled={fraudReason.trim().length < 10}>
                  Confirm Fraud Desk escalation
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowFraudBox(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          )}

          {app.fraud_flag && (
            <div className="space-y-3 border-t border-red-200 bg-red-50/60 p-5 text-sm">
              <p className="font-semibold text-red-900">
                Active Fraud Desk Escalation {app.fraud_escalated_at ? `(${formatDateTime(app.fraud_escalated_at)})` : ""}
              </p>
              <p className="text-red-800">{app.fraud_reason}</p>
              {can("fraud:review") && (
                <div className="space-y-2 pt-2">
                  <Input
                    aria-label="Fraud resolution justification"
                    value={fraudResolveText}
                    onChange={(e) => setFraudResolveText(e.target.value)}
                    placeholder="Fraud specialist findings (min 10 chars)…"
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={busy}
                      disabled={fraudResolveText.trim().length < 10}
                      onClick={() => void handleFraudResolve("CLEAR_FLAG")}
                    >
                      Clear fraud flag
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      loading={busy}
                      disabled={fraudResolveText.trim().length < 10}
                      onClick={() => void handleFraudResolve("CONFIRM_FRAUD_REJECT")}
                    >
                      Confirm fraud &amp; reject
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Submitted applicant baseline"
            description="Reference fields submitted by the applicant against which documents are cross-checked."
          />
          <dl className="grid gap-4 p-5 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <Fact label="Full name" value={app.full_name} />
            <Fact label="Date of birth" value={app.date_of_birth} />
            <Fact label="PAN" value={app.pan_number} />
            <Fact label="Aadhaar last 4" value={app.aadhaar_last4 ? `XXXX-XXXX-${app.aadhaar_last4}` : null} />
            <Fact label="Location" value={[app.city, app.state, app.pincode].filter(Boolean).join(", ")} />
            <Fact label="Education" value={[app.education_level, app.board_name, app.passing_year].filter(Boolean).join(" · ")} />
            <Fact label="Account holder" value={app.account_holder_name} />
            <Fact label="Bank & IFSC" value={[app.bank_name, app.ifsc_code, app.account_number_masked].filter(Boolean).join(" · ")} />
          </dl>
        </Card>

        <FieldComparisonCard application={app} report={report} />

        <Card>
          <CardHeader
            title="Uploaded source files"
            description="Aadhaar images are redacted automatically inside the verification panel below to avoid unmasked 12-digit display."
          />
          <div className="divide-y divide-slate-200">
            {app.documents.map((doc) => {
              const label = REQUIRED_DOCUMENTS.find((d) => d.type === doc.doc_type)?.label ?? doc.doc_type;
              const isAadhaar = doc.doc_type === "AADHAAR_FRONT" || doc.doc_type === "AADHAAR_BACK";
              return (
                <div key={doc.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-sm">
                  <div>
                    <p className="font-medium text-slate-900">{label}</p>
                    <p className="text-xs text-slate-500">
                      {doc.original_filename} · {formatBytes(doc.file_size_bytes)} · v{doc.version}
                    </p>
                  </div>
                  {isAadhaar ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700">
                      <ShieldCheck className="h-4 w-4" /> Use redacted viewer below
                    </span>
                  ) : (
                    <Button size="sm" variant="secondary" onClick={() => setPreviewDoc(doc)}>
                      <Eye className="h-4 w-4" /> View file
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        <VerificationReportPanel
          report={report}
          onReportChange={setReport}
          canRunProcessing
          canCorrectFields
        />

        <DecisionHistoryPanel
          summary={decisionSummary}
          onRefresh={load}
          canEvaluate
          canDecide={can("application:decide") || can("application:escalate")}
          canDecideEscalated={can("application:decide_escalated")}
        />

        {(app.status === "KYC_APPROVED" || app.status === "TRAINING_IN_PROGRESS" || app.status === "CERTIFIED") && (
          <TrainingStatusPanel applicationId={app.id} onApplicationStatusChanged={load} />
        )}
      </div>

      <DocumentPreviewModal applicationId={app.id} document={previewDoc} onClose={() => setPreviewDoc(null)} />
    </>
  );
}

function Fact({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-medium text-slate-900">{value || <span className="text-slate-400">Not provided</span>}</dd>
    </div>
  );
}
