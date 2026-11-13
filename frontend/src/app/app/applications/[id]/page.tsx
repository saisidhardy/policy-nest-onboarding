"use client";

import { ArrowRight, Eye, ScrollText } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationTracker } from "@/components/onboarding/ApplicationTracker";
import { DocumentPreviewModal } from "@/components/onboarding/DocumentPreviewModal";
import { DecisionHistoryPanel } from "@/components/verification/DecisionHistoryPanel";
import { TrainingStatusPanel } from "@/components/training/TrainingStatusPanel";
import { VerificationReportPanel } from "@/components/verification/VerificationReportPanel";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type {
  ApplicationDecisionSummary,
  ApplicationDetail,
  ApplicationDocument,
  ApplicationVerificationReport,
} from "@/lib/types";

export default function ApplicationDetailPage() {
  return (
    <RequirePermission permission="application:read_own">
      <ApplicationDetailView />
    </RequirePermission>
  );
}

function ApplicationDetailView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [verification, setVerification] = useState<ApplicationVerificationReport | null>(null);
  const [decisionSummary, setDecisionSummary] = useState<ApplicationDecisionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<ApplicationDocument | null>(null);

  const load = useCallback(async () => {
    try {
      const [data, ver, dec] = await Promise.all([
        api<ApplicationDetail>(`/applications/${id}`),
        api<ApplicationVerificationReport>(`/applications/${id}/verification`).catch(() => null),
        api<ApplicationDecisionSummary>(`/applications/${id}/decisions`).catch(() => null),
      ]);
      setApp(data);
      setVerification(ver);
      setDecisionSummary(dec);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load application.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function withdraw() {
    if (!app) return;
    setWithdrawing(true);
    try {
      const updated = await api<ApplicationDetail>(`/applications/${app.id}/withdraw`, {
        method: "POST",
        body: { reason: "Withdrawn by applicant" },
      });
      setApp(updated);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to withdraw draft.");
    } finally {
      setWithdrawing(false);
    }
  }

  if (error) return <Alert tone="error">{error}</Alert>;
  if (!app) return <Spinner label="Loading application details" />;

  const editable = app.status === "DRAFT" || app.status === "NEEDS_MORE_INFO";
  const docsByType = new Map(app.documents.filter((d) => d.is_current).map((d) => [d.doc_type, d]));

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Tracking · ${app.reference_code}`}
        description={`Created ${formatDateTime(app.created_at)}`}
        action={
          <div className="flex flex-wrap gap-2">
            {editable && (
              <Link
                href={`/app/onboarding/${app.id}`}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-700 px-4 text-sm font-medium text-white hover:bg-brand-800"
              >
                Resume step {app.current_step} <ArrowRight className="h-4 w-4" />
              </Link>
            )}
            {app.status === "CERTIFIED" && (
              <Button
                variant="secondary"
                onClick={() => window.open(`/api/v1/applications/${app.id}/dossier?format=html`, "_blank")}
              >
                <ScrollText className="h-4 w-4" /> Official Dossier
              </Button>
            )}
            {app.status === "DRAFT" && (
              <Button variant="secondary" loading={withdrawing} onClick={withdraw}>
                Withdraw draft
              </Button>
            )}
          </div>
        }
      />

      <ApplicationTracker application={app} />

      <DecisionHistoryPanel
        summary={decisionSummary}
        onRefresh={load}
        onReapplied={(child) => router.push(`/app/onboarding/${child.id}`)}
        canEvaluate={app.status === "SUBMITTED" || app.status === "REWORK_SUBMITTED"}
        isApplicantOwner
      />

      {(app.status === "KYC_APPROVED" || app.status === "TRAINING_IN_PROGRESS" || app.status === "CERTIFIED") && (
        <TrainingStatusPanel applicationId={app.id} onApplicationStatusChanged={load} />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Submitted profile & KYC summary" />
          <dl className="divide-y divide-slate-100 text-sm">
            <InfoRow label="Full name" value={app.full_name} />
            <InfoRow label="Date of birth" value={app.date_of_birth} />
            <InfoRow label="PAN" value={app.pan_number} />
            <InfoRow label="Aadhaar" value={app.aadhaar_last4 ? `XXXX-XXXX-${app.aadhaar_last4}` : null} />
            <InfoRow label="Residential state" value={app.state ? `${app.state} (${app.region ?? ""})` : null} />
            <InfoRow label="Education" value={app.education_level ? `${app.education_level} · ${app.board_name ?? ""}` : null} />
            <InfoRow label="Bank & IFSC" value={app.bank_name ? `${app.bank_name} · ${app.ifsc_code ?? ""}` : null} />
            <InfoRow label="Account number" value={app.account_number_masked} />
          </dl>
        </Card>

        <Card>
          <CardHeader title="Uploaded documents" description="Stored privately and served only to authorised users." />
          <ul className="divide-y divide-slate-100">
            {REQUIRED_DOCUMENTS.map((spec) => {
              const doc = docsByType.get(spec.type);
              return (
                <li key={spec.type} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-sm">
                  <div>
                    <p className="font-medium text-slate-900">{spec.label}</p>
                    <p className="text-xs text-slate-500">
                      {doc ? `${doc.original_filename} · ${formatBytes(doc.file_size_bytes)} · v${doc.version}` : "Not uploaded"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {doc ? <Badge tone="success">{doc.status}</Badge> : <Badge tone="neutral">Missing</Badge>}
                    {doc && (
                      <Button variant="ghost" size="sm" onClick={() => setPreviewDoc(doc)}>
                        <Eye className="h-3.5 w-3.5" /> View
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      <div className="mt-6">
        <VerificationReportPanel
          report={verification}
          onReportChange={setVerification}
          canRunProcessing={app.documents.length > 0 && (app.status === "DRAFT" || app.status === "NEEDS_MORE_INFO" || (verification?.extractions.length ?? 0) === 0)}
          canCorrectFields={false}
        />
      </div>

      <DocumentPreviewModal applicationId={app.id} document={previewDoc} onClose={() => setPreviewDoc(null)} />
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid grid-cols-3 gap-3 px-5 py-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="col-span-2 font-medium text-slate-900">{value || <span className="font-normal text-slate-400">—</span>}</dd>
    </div>
  );
}
