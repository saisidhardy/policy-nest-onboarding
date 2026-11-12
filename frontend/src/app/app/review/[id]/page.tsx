"use client";

import { ArrowLeft, Eye, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { DocumentPreviewModal } from "@/components/onboarding/DocumentPreviewModal";
import { DecisionHistoryPanel } from "@/components/verification/DecisionHistoryPanel";
import { VerificationReportPanel } from "@/components/verification/VerificationReportPanel";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type {
  ApplicationDecisionSummary,
  ApplicationDetail,
  ApplicationDocument,
  ApplicationVerificationReport,
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
  const { can } = useAuth();
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [report, setReport] = useState<ApplicationVerificationReport | null>(null);
  const [decisionSummary, setDecisionSummary] = useState<ApplicationDecisionSummary | null>(null);
  const [previewDoc, setPreviewDoc] = useState<ApplicationDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [appData, repData, decData] = await Promise.all([
        api<ApplicationDetail>(`/applications/${id}`),
        api<ApplicationVerificationReport>(`/applications/${id}/verification`),
        api<ApplicationDecisionSummary>(`/applications/${id}/decisions`).catch(() => null),
      ]);
      setApp(appData);
      setReport(repData);
      setDecisionSummary(decData);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load application verification details.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <Alert tone="error">{error}</Alert>
        <Link href="/app/review" className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back to document desk
        </Link>
      </div>
    );
  }
  if (!app) return <Spinner label="Loading application review" />;

  return (
    <>
      <div className="mb-4">
        <Link href="/app/review" className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" /> All applications
        </Link>
      </div>

      <PageHeader
        title={`${app.reference_code} · ${app.full_name || "Applicant"}`}
        description={`Submitted ${app.submitted_at ? formatDateTime(app.submitted_at) : "Draft"} · Region: ${app.region ?? "Unassigned"}`}
        action={
          <div className="flex items-center gap-2">
            <ApplicationStatusBadge status={app.status} />
            <Badge tone="neutral">Clearance {app.sensitivity}</Badge>
          </div>
        }
      />

      <div className="space-y-6">
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
