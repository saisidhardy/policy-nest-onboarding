"use client";

import clsx from "clsx";
import { Check, History } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Button, PageHeader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { WIZARD_STEPS } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type { ApplicationDetail, RuleExecution } from "@/lib/types";
import { AddressStep } from "./AddressStep";
import { ApplicationStatusBadge } from "./ApplicationTracker";
import { BankStep } from "./BankStep";
import { DocumentsStep } from "./DocumentsStep";
import { EducationStep } from "./EducationStep";
import { PersonalStep } from "./PersonalStep";
import { ReviewStep } from "./ReviewStep";

export function OnboardingWizard({
  application,
  onUpdated,
  onReload,
}: {
  application: ApplicationDetail;
  onUpdated: (app: ApplicationDetail) => void;
  onReload: () => Promise<void>;
}) {
  const router = useRouter();
  const [step, setStep] = useState<number>(application.current_step || 1);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  async function saveDraft(payload: Record<string, unknown>, nextStep?: number) {
    setSaving(true);
    setError(null);
    setFieldErrors({});
    setSavedNotice(null);
    const targetStep = nextStep ?? step;
    try {
      const updated = await api<ApplicationDetail>(`/applications/${application.id}`, {
        method: "PATCH",
        body: { ...payload, current_step: targetStep },
      });
      onUpdated(updated);
      setStep(targetStep);
      setSavedNotice(nextStep && nextStep !== step ? `Draft saved. Moved to step ${targetStep}.` : "Draft saved.");
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors(err.fieldErrors);
        setError(err.message);
      } else {
        setError("Failed to save draft.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function submitApp(consents: {
    consent_terms: boolean;
    consent_kyc_processing: boolean;
    declaration_no_other_posp: boolean;
  }) {
    setSubmitting(true);
    setError(null);
    try {
      const submitted = await api<ApplicationDetail>(`/applications/${application.id}/submit`, {
        method: "POST",
        body: consents,
      });
      await api<RuleExecution>(`/applications/${submitted.id}/evaluate`, {
        method: "POST",
        body: { apply_transition: true, trigger_source: "AUTO_SUBMIT" },
      }).catch(() => null);
      const updated = await api<ApplicationDetail>(`/applications/${submitted.id}`).catch(() => submitted);
      onUpdated(updated);
      router.push(`/app/applications/${updated.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit application.");
    } finally {
      setSubmitting(false);
    }
  }

  async function withdrawDraft() {
    setWithdrawing(true);
    setError(null);
    try {
      const withdrawn = await api<ApplicationDetail>(`/applications/${application.id}/withdraw`, {
        method: "POST",
        body: { reason: "Withdrawn by applicant from onboarding wizard" },
      });
      onUpdated(withdrawn);
      router.push("/app/applications");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not withdraw draft.");
    } finally {
      setWithdrawing(false);
    }
  }

  const sectionFlags: Record<string, boolean> = {
    personal: application.completeness.sections.personal,
    address: application.completeness.sections.address,
    education: application.completeness.sections.education,
    bank: application.completeness.sections.bank,
    documents: application.completeness.sections.documents,
    review: application.completeness.sections.declarations,
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={`POSP Onboarding · ${application.reference_code}`}
        description={`Last saved ${formatDateTime(application.last_saved_at)} · ${application.completeness.completed_sections} of ${application.completeness.total_sections} sections complete`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <ApplicationStatusBadge status={application.status} />
            <Link
              href={`/app/applications/${application.id}`}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <History className="h-3.5 w-3.5" /> History & tracking
            </Link>
            {application.status === "DRAFT" && (
              <Button type="button" variant="ghost" size="sm" loading={withdrawing} onClick={withdrawDraft}>
                Withdraw draft
              </Button>
            )}
          </div>
        }
      />

      <nav aria-label="Onboarding steps" className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {WIZARD_STEPS.map((s) => {
          const active = step === s.step;
          const done = sectionFlags[s.key];
          return (
            <button
              key={s.step}
              type="button"
              onClick={() => {
                setError(null);
                setFieldErrors({});
                setSavedNotice(null);
                setStep(s.step);
              }}
              className={clsx(
                "flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition",
                active
                  ? "border-brand-600 bg-brand-50 text-brand-900"
                  : done
                    ? "border-emerald-200 bg-white text-slate-800 hover:border-emerald-300"
                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300",
              )}
            >
              <span
                className={clsx(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  active
                    ? "bg-brand-700 text-white"
                    : done
                      ? "bg-emerald-600 text-white"
                      : "bg-slate-100 text-slate-600",
                )}
              >
                {done && !active ? <Check className="h-3.5 w-3.5" /> : s.step}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-xs font-semibold">{s.title}</span>
                <span className="block truncate text-[11px] text-slate-500">{s.subtitle}</span>
              </span>
            </button>
          );
        })}
      </nav>

      {savedNotice && <Alert tone="success">{savedNotice}</Alert>}

      {step === 1 && (
        <PersonalStep
          key={`p-${application.updated_at}`}
          application={application}
          saving={saving}
          error={error}
          fieldErrors={fieldErrors}
          onSave={saveDraft}
        />
      )}
      {step === 2 && (
        <AddressStep
          key={`a-${application.updated_at}`}
          application={application}
          saving={saving}
          error={error}
          fieldErrors={fieldErrors}
          onSave={saveDraft}
          onBack={() => setStep(1)}
        />
      )}
      {step === 3 && (
        <EducationStep
          key={`e-${application.updated_at}`}
          application={application}
          saving={saving}
          error={error}
          fieldErrors={fieldErrors}
          onSave={saveDraft}
          onBack={() => setStep(2)}
        />
      )}
      {step === 4 && (
        <BankStep
          key={`b-${application.updated_at}`}
          application={application}
          saving={saving}
          error={error}
          fieldErrors={fieldErrors}
          onSave={saveDraft}
          onBack={() => setStep(3)}
        />
      )}
      {step === 5 && (
        <DocumentsStep
          application={application}
          onReload={onReload}
          onBack={() => setStep(4)}
          onContinue={() => {
            setSavedNotice(null);
            setStep(6);
          }}
        />
      )}
      {step === 6 && (
        <ReviewStep
          application={application}
          submitting={submitting}
          error={error}
          onJumpToStep={(target) => {
            setError(null);
            setStep(target);
          }}
          onSubmit={submitApp}
          onBack={() => setStep(5)}
        />
      )}
    </div>
  );
}
