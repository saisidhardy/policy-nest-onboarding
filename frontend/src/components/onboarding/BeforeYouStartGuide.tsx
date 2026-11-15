"use client";

import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Lock,
  Shield,
  Smartphone,
  Sparkles,
  Users,
} from "lucide-react";
import React, { useState } from "react";
import { Button } from "@/components/ui";
import { JOURNEY_STAGES } from "@/lib/documentGuidance";
import type { ApplicationDetail } from "@/lib/types";
import { DocumentReadinessChecklist } from "./DocumentReadinessChecklist";

export interface BeforeYouStartGuideProps {
  application?: ApplicationDetail | null;
  onStartOrResume: () => void;
  onClose?: () => void;
  isModal?: boolean;
}

export function BeforeYouStartGuide({
  application,
  onStartOrResume,
  onClose,
}: BeforeYouStartGuideProps) {
  const [activeTab, setActiveTab] = useState<"checklist" | "privacy" | "journey">("checklist");

  const hasStarted = Boolean(application && application.current_step > 1);

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-fadeIn" aria-label="Before you start preparation guide">
      {/* Header Banner */}
      <div className="rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50 via-white to-emerald-50/40 p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-brand-100/80 px-3 py-1 text-xs font-bold text-brand-900">
              <Sparkles className="h-3.5 w-3.5 text-brand-700" />
              <span>POSP Applicant Preparation Guide</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Get ready for your POSP onboarding
            </h1>
            <p className="text-sm text-slate-600 max-w-2xl leading-relaxed">
              Taking 5 minutes to gather your 6 documents now ensures your application is verified on the first attempt without rework delays.
            </p>
          </div>

          <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 bg-white/90 border border-slate-200 px-3 py-1.5 rounded-lg shadow-2xs">
              <Clock className="h-4 w-4 text-emerald-600" />
              <span>Estimated time: ~15 mins</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 bg-white/90 border border-slate-200 px-3 py-1.5 rounded-lg shadow-2xs">
              <Smartphone className="h-4 w-4 text-brand-600" />
              <span>Autosaves across devices</span>
            </div>
          </div>
        </div>

        {application?.reference_code && (
          <div className="mt-4 pt-4 border-t border-brand-100 flex items-center justify-between text-xs text-slate-600">
            <span>
              Application Reference: <strong className="font-mono text-slate-900">{application.reference_code}</strong>
            </span>
            <span className="text-emerald-700 font-semibold flex items-center gap-1">
              <CheckCircle2 className="h-3.5 w-3.5" /> Progress saved in secure cloud
            </span>
          </div>
        )}
      </div>

      {/* Navigation Tabs for Progressive Disclosure */}
      <div className="flex border-b border-slate-200 text-sm font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab("checklist")}
          className={`pb-3 px-4 border-b-2 transition-colors ${
            activeTab === "checklist"
              ? "border-brand-700 text-brand-700 font-bold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          1. Six Required Documents
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("journey")}
          className={`pb-3 px-4 border-b-2 transition-colors ${
            activeTab === "journey"
              ? "border-brand-700 text-brand-700 font-bold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          2. How Onboarding Works
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("privacy")}
          className={`pb-3 px-4 border-b-2 transition-colors ${
            activeTab === "privacy"
              ? "border-brand-700 text-brand-700 font-bold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          3. Privacy & Saving Guarantee
        </button>
      </div>

      {/* Tab 1: Six Required Documents */}
      {activeTab === "checklist" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Have these 6 items ready</h2>
              <p className="text-xs text-slate-600">
                Click any document to view required fields, photography tips, and common pitfalls to avoid.
              </p>
            </div>
            <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
              6 mandatory documents
            </span>
          </div>

          <DocumentReadinessChecklist
            documents={application?.documents || []}
            showExpandableGuidance={true}
          />

          <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-xs text-amber-950 space-y-1.5">
            <p className="font-bold flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-amber-700" /> Photography Rule: Good photos pass the first time
            </p>
            <p className="text-amber-900">
              Take photos in natural daylight or under a bright room lamp. Turn your phone’s camera flash <strong>OFF</strong> to prevent glare on plastic laminate cards, and ensure all <strong>four corners</strong> are inside the photo.
            </p>
          </div>
        </div>
      )}

      {/* Tab 2: How Onboarding Works */}
      {activeTab === "journey" && (
        <div className="space-y-5">
          <div>
            <h2 className="text-lg font-bold text-slate-900">The 6-stage certification journey</h2>
            <p className="text-xs text-slate-600">
              Clear statutory path under IRDAI Point of Sales Person (POSP) regulations.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {JOURNEY_STAGES.map((s) => (
              <div
                key={s.id}
                className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 hover:border-brand-300 transition-all shadow-2xs"
              >
                <div className="flex items-center justify-between">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-900">
                    {s.stage}
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">{s.regulatoryNote}</span>
                </div>
                <h3 className="text-sm font-bold text-slate-900">{s.applicantLabel}</h3>
                <p className="text-xs text-slate-600 leading-relaxed">{s.summary}</p>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700 space-y-2">
            <p className="font-bold text-slate-900">What happens after you submit?</p>
            <p>
              1. <strong>Instant automated validation:</strong> NSDL validates your PAN and NPCI validates your bank account via penny-drop or Account Aggregator.
            </p>
            <p>
              2. <strong>Human review safeguards:</strong> Legitimate regional name variations, maiden names, or joint accounts where you are the first holder are not automatically rejected; they are routed to a human reviewer.
            </p>
            <p>
              3. <strong>Immediate notification:</strong> If any photo is unclear, you will receive an SMS and WhatsApp alert with exact instructions on how to fix only that specific document without restarting.
            </p>
          </div>
        </div>
      )}

      {/* Tab 3: Privacy & Saving Guarantee */}
      {activeTab === "privacy" && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">How your data is protected</h2>
            <p className="text-xs text-slate-600">
              Built on production-grade security and DPDP Act 2023 compliance standards.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-2xs">
              <div className="flex items-center gap-2 text-emerald-700 font-bold text-sm">
                <Shield className="h-4 w-4" />
                <span>Aadhaar Data Minimization</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Per UIDAI and DPDP Act rules, the first 8 digits of your Aadhaar card are masked automatically upon ingestion. Only the last 4 digits (XXXX-XXXX-1234) are stored.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-2xs">
              <div className="flex items-center gap-2 text-brand-700 font-bold text-sm">
                <Lock className="h-4 w-4" />
                <span>AES-256 Storage & Signed URLs</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                All document uploads are encrypted at rest with AES-256 in private cloud buckets. Document links expire in 15 minutes and cannot be accessed publicly.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-2xs">
              <div className="flex items-center gap-2 text-indigo-700 font-bold text-sm">
                <Smartphone className="h-4 w-4" />
                <span>Cross-Device Continuous Autosave</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Every field and document upload is persisted immediately to your authenticated Railway account. You can start on your phone, upload photos, and continue on your laptop seamlessly.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-2xs">
              <div className="flex items-center gap-2 text-amber-700 font-bold text-sm">
                <Users className="h-4 w-4" />
                <span>AI Copilot Privacy Boundary</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Document photos and confidential tax IDs are never sent to external AI models. The AI Copilot provides guidance strictly grounded in the official POSP manual.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="pt-4 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="text-xs text-slate-500">
          Need assistance at any step? Tap the floating <strong className="text-brand-800">Ask PolicyNest</strong> Copilot in the bottom-right corner.
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          {onClose && (
            <Button type="button" variant="ghost" size="md" onClick={onClose} className="w-full sm:w-auto">
              Close guide
            </Button>
          )}
          <Button
            type="button"
            variant="primary"
            size="md"
            onClick={onStartOrResume}
            className="w-full sm:w-auto bg-brand-700 hover:bg-brand-800 text-white font-bold gap-2 shadow-sm"
          >
            <span>{hasStarted ? "Continue to Application" : "Start Application"}</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
