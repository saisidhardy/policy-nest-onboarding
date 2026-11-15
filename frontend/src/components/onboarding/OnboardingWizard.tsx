"use client";

import clsx from "clsx";
import {
  BookOpen,
  Check,
  History,
  Shield,
  Timer,
  UploadCloud,
  X,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Button, PageHeader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { WIZARD_STEPS } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { ApplicationDetail, RuleExecution } from "@/lib/types";
import { PrivacyDisclosureModal } from "../compliance/PrivacyDisclosureModal";
import { AddressStep } from "./AddressStep";
import { ApplicationStatusBadge } from "./ApplicationTracker";
import { BankStep } from "./BankStep";
import { BeforeYouStartGuide } from "./BeforeYouStartGuide";
import { DocumentsStep } from "./DocumentsStep";
import { EducationStep } from "./EducationStep";
import { KeepTheseReadyPanel } from "./KeepTheseReadyPanel";
import { PersonalStep } from "./PersonalStep";
import { ReviewStep } from "./ReviewStep";
import { ThirtyMinuteOnboardingSession } from "./ThirtyMinuteOnboardingSession";

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
  const { t } = useI18n();
  const [step, setStep] = useState<number>(application.current_step || 1);
  const [sessionMode, setSessionMode] = useState<boolean>(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [showPrepModal, setShowPrepModal] = useState(false);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

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

  if (sessionMode) {
    return (
      <ThirtyMinuteOnboardingSession
        application={application}
        onReload={onReload}
        onExit={() => setSessionMode(false)}
        onComplete={() => {
          setSessionMode(false);
          setStep(6);
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`POSP Onboarding · ${application.reference_code}`}
        description={`Last saved ${formatDateTime(application.last_saved_at)} · ${application.completeness.completed_sections} of ${application.completeness.total_sections} sections complete`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowPrepModal(true)}
              className="text-xs text-slate-700 hover:text-slate-900 border border-slate-200"
            >
              <BookOpen className="h-3.5 w-3.5 mr-1 text-brand-700" /> Prep guide
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowPrivacyModal(true)}
              className="text-xs text-slate-700 hover:text-slate-900 border border-slate-200"
            >
              <Shield className="h-3.5 w-3.5 mr-1 text-emerald-700" /> Privacy notice
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => setSessionMode(true)}
              className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
            >
              <Timer className="h-3.5 w-3.5" /> 30-Min Session
            </Button>
            <ApplicationStatusBadge status={application.status} />
            <Link
              href={`/app/applications/${application.id}`}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <History className="h-3.5 w-3.5" /> History &amp; tracking
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
          const localizedTitle = (
            {
              1: t.wizard.step1_title,
              2: t.wizard.step2_title,
              3: t.wizard.step3_title,
              4: t.wizard.step4_title,
              5: t.wizard.step5_title,
              6: t.wizard.step6_title,
            } as Record<number, string>
          )[s.step] ?? s.title;

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
                  ? "border-brand-600 bg-brand-50 text-brand-900 shadow-2xs font-bold"
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
                <span className="block truncate text-xs font-semibold">{localizedTitle}</span>
                <span className="block truncate text-[11px] text-slate-500">{s.subtitle}</span>
              </span>
            </button>
          );
        })}
      </nav>

      {savedNotice && <Alert tone="success">{savedNotice}</Alert>}

      {application.status === "DRAFT" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-300 bg-emerald-50/70 p-4 text-sm shadow-sm">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-white">
              <Timer className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <p className="font-bold text-emerald-950">30-Minute Fast-Track Onboarding Session</p>
                <span className="rounded-full bg-emerald-200/70 px-2 py-0.5 text-[11px] font-semibold text-emerald-900">
                  Recommended UX
                </span>
              </div>
              <p className="text-xs text-emerald-800 mt-0.5">
                Complete all 6 mandatory compliance documents in one focused, distraction-free guided session with live quality checks and continuous timer.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => setSessionMode(true)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
            >
              <Zap className="h-4 w-4 mr-1.5" /> Start 30-Minute Session
            </Button>
            {step < 5 && (
              <Button type="button" variant="secondary" size="sm" onClick={() => setStep(5)}>
                <UploadCloud className="h-4 w-4 mr-1.5" /> Jump to Docs
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Main Grid: Dominant Form on Left, Contextual Side Panel on Right (Workstream G, I, O) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 xl:col-span-9 space-y-6">
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
              onApplyAutofill={async (patch, targetStep) => {
                await saveDraft(patch, targetStep ?? 5);
              }}
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

        {/* Collapsible Contextual Side Panel (Workstream I) */}
        <aside className="lg:col-span-4 xl:col-span-3 space-y-4">
          <KeepTheseReadyPanel
            currentStep={step}
            documents={application.documents}
            onOpenPreparationGuide={() => setShowPrepModal(true)}
          />
        </aside>
      </div>

      {/* Preparation Guide Modal Dialog */}
      {showPrepModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fadeIn"
        >
          <div className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-xl border border-slate-200">
            <button
              type="button"
              onClick={() => setShowPrepModal(false)}
              aria-label="Close preparation guide"
              className="absolute top-4 right-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
            >
              <X className="h-5 w-5" />
            </button>
            <BeforeYouStartGuide
              application={application}
              onStartOrResume={() => setShowPrepModal(false)}
              onClose={() => setShowPrepModal(false)}
              isModal={true}
            />
          </div>
        </div>
      )}

      {/* Privacy Disclosure Modal Dialog */}
      <PrivacyDisclosureModal isOpen={showPrivacyModal} onClose={() => setShowPrivacyModal(false)} />
    </div>
  );
}
