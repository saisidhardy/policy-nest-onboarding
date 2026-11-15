"use client";

import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  Pencil,
} from "lucide-react";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader } from "@/components/ui";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import type { ApplicationDetail, ApplicationDocument } from "@/lib/types";
import { DocumentPreviewModal } from "./DocumentPreviewModal";

export function ReviewStep({
  application,
  submitting,
  error,
  onJumpToStep,
  onSubmit,
  onBack,
}: {
  application: ApplicationDetail;
  submitting: boolean;
  error: string | null;
  onJumpToStep: (step: number) => void;
  onSubmit: (consents: {
    consent_terms: boolean;
    consent_kyc_processing: boolean;
    declaration_no_other_posp: boolean;
  }) => Promise<void>;
  onBack: () => void;
}) {
  const [page, setPage] = useState<1 | 2 | 3>(1);
  const [consentTerms, setConsentTerms] = useState(application.consent_terms);
  const [consentKyc, setConsentKyc] = useState(application.consent_kyc_processing);
  const [noOtherPosp, setNoOtherPosp] = useState(application.declaration_no_other_posp);
  const [previewDoc, setPreviewDoc] = useState<ApplicationDocument | null>(null);

  const comp = application.completeness;
  const allConsents = consentTerms && consentKyc && noOtherPosp;
  const docsByType = new Map(application.documents.filter((d) => d.is_current).map((d) => [d.doc_type, d]));

  return (
    <>
      <Card>
        <CardHeader
          title="Step 6: Review & submit"
          description={
            page === 1
              ? "Page 1 of 3: Verify your personal, address, education, and bank details."
              : page === 2
              ? "Page 2 of 3: Inspect all 6 uploaded documents and verification readiness."
              : "Page 3 of 3: Statutory applicant declarations, KYC processing consent, and final submission."
          }
          action={
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
              <span>Page {page} of 3</span>
            </div>
          }
        />

        {/* Sub-page Navigation Tabs */}
        <div className="flex border-b border-slate-100 bg-slate-50/50 px-5 pt-3 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setPage(1)}
            className={`pb-2.5 px-3 border-b-2 transition ${
              page === 1
                ? "border-brand-700 text-brand-800 font-bold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            1. Details Summary
          </button>
          <button
            type="button"
            onClick={() => setPage(2)}
            className={`pb-2.5 px-3 border-b-2 transition ${
              page === 2
                ? "border-brand-700 text-brand-800 font-bold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            2. Documents ({docsByType.size}/6)
          </button>
          <button
            type="button"
            onClick={() => setPage(3)}
            className={`pb-2.5 px-3 border-b-2 transition ${
              page === 3
                ? "border-brand-700 text-brand-800 font-bold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            3. Declarations &amp; Submit
          </button>
        </div>

        <div className="space-y-6 px-5 py-5">
          {error && <Alert tone="error">{error}</Alert>}

          {!comp.ready_to_submit && (
            <Alert tone="warning" title="Complete required items before submitting">
              {comp.missing_fields.length > 0 && (
                <p className="text-xs">Missing fields: {comp.missing_fields.join(", ")}</p>
              )}
              {comp.missing_documents.length > 0 && (
                <p className="mt-1 text-xs">
                  Missing documents:{" "}
                  {comp.missing_documents
                    .map((t) => REQUIRED_DOCUMENTS.find((d) => d.type === t)?.label ?? t)
                    .join(", ")}
                </p>
              )}
            </Alert>
          )}

          {/* Page 1: Details Summary */}
          {page === 1 && (
            <div className="space-y-4 animate-fadeIn">
              <div className="grid gap-4 lg:grid-cols-2">
                <SummarySection title="1. Personal details" complete={comp.sections.personal} onEdit={() => onJumpToStep(1)}>
                  <SummaryRow label="Full name" value={application.full_name} />
                  <SummaryRow label="Date of birth" value={application.date_of_birth} />
                  <SummaryRow label="Gender" value={application.gender} />
                  <SummaryRow label="Father / spouse" value={application.father_or_spouse_name} />
                  <SummaryRow label="Mobile" value={application.mobile} />
                  <SummaryRow label="Email" value={application.email} />
                  <SummaryRow label="PAN" value={application.pan_number} />
                  <SummaryRow label="Aadhaar (masked)" value={application.aadhaar_last4 ? `XXXX-XXXX-${application.aadhaar_last4}` : null} />
                </SummarySection>

                <SummarySection title="2. Address details" complete={comp.sections.address} onEdit={() => onJumpToStep(2)}>
                  <SummaryRow
                    label="Residential"
                    value={
                      application.address_line1
                        ? `${application.address_line1}${application.address_line2 ? `, ${application.address_line2}` : ""}, ${application.city ?? ""}, ${application.district ?? ""}, ${application.state ?? ""} - ${application.pincode ?? ""}`
                        : null
                    }
                  />
                  <SummaryRow label="Region" value={application.region} />
                  <SummaryRow
                    label="Permanent"
                    value={
                      application.same_as_permanent
                        ? "Same as residential"
                        : `${application.permanent_address_line1 ?? ""}, ${application.permanent_city ?? ""}, ${application.permanent_state ?? ""} - ${application.permanent_pincode ?? ""}`
                    }
                  />
                </SummarySection>

                <SummarySection title="3. Education details" complete={comp.sections.education} onEdit={() => onJumpToStep(3)}>
                  <SummaryRow label="Level" value={application.education_level} />
                  <SummaryRow label="Board" value={application.board_name} />
                  <SummaryRow label="Institution" value={application.school_or_university} />
                  <SummaryRow label="Passing year" value={application.passing_year ? String(application.passing_year) : null} />
                  <SummaryRow label="Roll number" value={application.roll_number} />
                  <SummaryRow label="Result" value={application.result_status} />
                </SummarySection>

                <SummarySection title="4. Bank details" complete={comp.sections.bank} onEdit={() => onJumpToStep(4)}>
                  <SummaryRow label="Account holder" value={application.account_holder_name} />
                  <SummaryRow label="Bank" value={application.bank_name} />
                  <SummaryRow label="IFSC" value={application.ifsc_code} />
                  <SummaryRow label="Account number" value={application.account_number_masked} />
                  <SummaryRow label="Type" value={application.account_type} />
                  <SummaryRow
                    label="Joint account"
                    value={application.is_joint_account ? (application.is_primary_holder ? "Yes (Primary holder)" : "Yes (Secondary)") : "No"}
                  />
                </SummarySection>
              </div>

              <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
                <Button type="button" variant="secondary" onClick={onBack}>
                  <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Documents
                </Button>
                <Button type="button" onClick={() => setPage(2)}>
                  <span>Next: Check Documents (Page 2 of 3)</span>
                  <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              </div>
            </div>
          )}

          {/* Page 2: Documents Verification */}
          {page === 2 && (
            <div className="space-y-4 animate-fadeIn">
              <SummarySection title="5. Uploaded documents (6 required)" complete={comp.sections.documents} onEdit={() => onJumpToStep(5)}>
                <div className="divide-y divide-slate-100">
                  {REQUIRED_DOCUMENTS.map((spec) => {
                    const doc = docsByType.get(spec.type);
                    return (
                      <div key={spec.type} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                        <div>
                          <p className="font-medium text-slate-900">{spec.label}</p>
                          <p className="text-xs text-slate-500">
                            {doc ? `${doc.original_filename} · ${formatBytes(doc.file_size_bytes)} · v${doc.version}` : "Not uploaded"}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {doc ? <Badge tone="success">Ready</Badge> : <Badge tone="warning">Missing</Badge>}
                          {doc && (
                            <Button type="button" variant="ghost" size="sm" onClick={() => setPreviewDoc(doc)}>
                              <Eye className="h-3.5 w-3.5" /> View
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </SummarySection>

              <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
                <Button type="button" variant="secondary" onClick={() => setPage(1)}>
                  <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Page 1
                </Button>
                <Button type="button" onClick={() => setPage(3)}>
                  <span>Next: Declarations &amp; Submit (Page 3 of 3)</span>
                  <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              </div>
            </div>
          )}

          {/* Page 3: Declarations and Submit */}
          {page === 3 && (
            <div className="space-y-4 animate-fadeIn">
              <form
                className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5"
                onSubmit={(e) => {
                  e.preventDefault();
                  void onSubmit({
                    consent_terms: consentTerms,
                    consent_kyc_processing: consentKyc,
                    declaration_no_other_posp: noOtherPosp,
                  });
                }}
              >
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Applicant statutory declarations</h3>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Please read and confirm each statutory declaration required by IRDAI and DPDP Act 2023.
                  </p>
                </div>

                <div className="space-y-3 pt-2">
                  <label className="flex items-start gap-2.5 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={consentTerms}
                      onChange={(e) => setConsentTerms(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700"
                    />
                    <span>I confirm that all personal, education, bank, and identity details submitted are true, accurate, and belong to me.</span>
                  </label>

                  <label className="flex items-start gap-2.5 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={consentKyc}
                      onChange={(e) => setConsentKyc(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700"
                    />
                    <span>I consent to PolicyNest securely processing my uploaded documents and KYC data for IRDAI POSP onboarding under the Digital Personal Data Protection (DPDP) Act, 2023.</span>
                  </label>

                  <label className="flex items-start gap-2.5 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={noOtherPosp}
                      onChange={(e) => setNoOtherPosp(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700"
                    />
                    <span>I declare that I am not currently active as a POSP with another insurer or insurance intermediary without a valid NOC from the previous insurer.</span>
                  </label>
                </div>

                <div className="flex flex-wrap justify-between gap-3 border-t border-slate-200 pt-4">
                  <Button type="button" variant="secondary" onClick={() => setPage(2)}>
                    <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Documents
                  </Button>
                  <Button type="submit" loading={submitting} disabled={!comp.ready_to_submit || !allConsents}>
                    <CheckCircle2 className="h-4 w-4 mr-1.5" /> Submit application
                  </Button>
                </div>
              </form>
            </div>
          )}
        </div>
      </Card>

      <DocumentPreviewModal applicationId={application.id} document={previewDoc} onClose={() => setPreviewDoc(null)} />
    </>
  );
}

function SummarySection({
  title,
  complete,
  onEdit,
  children,
}: {
  title: string;
  complete: boolean;
  onEdit: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <Badge tone={complete ? "success" : "warning"}>{complete ? "Complete" : "Incomplete"}</Badge>
        </div>
        <button type="button" onClick={onEdit} className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
          <Pencil className="h-3 w-3" /> Edit
        </button>
      </div>
      <dl className="space-y-1.5 text-sm">{children}</dl>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="col-span-2 break-words text-xs font-medium text-slate-900">{value || <span className="text-slate-400">Not provided</span>}</dd>
    </div>
  );
}
