"use client";

import {
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Loader2,
  ShieldCheck,
  Upload,
} from "lucide-react";
import React from "react";
import { DOCUMENT_GUIDANCE_MAP } from "@/lib/documentGuidance";
import type { DocumentExtraction, DocumentType } from "@/lib/types";

export type UploadState =
  | "WAITING"
  | "UPLOADING"
  | "UPLOAD_COMPLETE"
  | "READING_DOCUMENT"
  | "QUALITY_CHECK"
  | "VERIFICATION_IN_PROGRESS"
  | "PASSED"
  | "CORRECTION_REQUIRED"
  | "HUMAN_REVIEW"
  | "SERVICE_UNAVAILABLE"
  | "FAILED";

export interface DocumentFeedbackCardProps {
  docType: DocumentType;
  uploadState?: UploadState;
  qualityStatus?: string;
  extraction?: DocumentExtraction | null;
  customError?: string | null;
  onUploadBetterImage?: () => void;
  onAskCopilot?: () => void;
}

export function DocumentFeedbackCard({
  docType,
  uploadState = "WAITING",
  qualityStatus,
  extraction,
  customError,
  onUploadBetterImage,
  onAskCopilot,
}: DocumentFeedbackCardProps) {
  const guide = DOCUMENT_GUIDANCE_MAP[docType];

  // Derive active status
  let effectiveState: UploadState = uploadState;
  if (customError) {
    effectiveState = "CORRECTION_REQUIRED";
  } else if (qualityStatus && qualityStatus !== "OK") {
    effectiveState = "CORRECTION_REQUIRED";
  } else if (extraction?.classification_match === false) {
    effectiveState = "CORRECTION_REQUIRED";
  }

  // 1. PASSED / VERIFIED AUTOMATICALLY
  if (effectiveState === "PASSED" || (extraction && extraction.quality_status === "OK" && !customError)) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3.5 text-xs text-emerald-950 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <span className="font-bold text-emerald-900">Verified automatically</span>
          </div>
          <span className="rounded-full bg-emerald-100 text-emerald-800 px-2 py-0.5 text-[11px] font-semibold">
            Quality OK
          </span>
        </div>
        <p className="text-emerald-800 leading-relaxed">
          Your {guide.shortLabel} passed quality and statutory format checks. Document data is securely encrypted.
        </p>
      </div>
    );
  }

  // 2. CORRECTION REQUIRED
  if (effectiveState === "CORRECTION_REQUIRED") {
    const whatIsWrong = customError || (qualityStatus === "IMAGE_BLURRY"
      ? "The image appears blurry or low-resolution."
      : qualityStatus === "IMAGE_GLARE"
      ? "Camera flash created glare reflections obscuring text."
      : qualityStatus === "IMAGE_CROPPED"
      ? "Outer borders or corners of the card appear cropped."
      : qualityStatus === "FACE_NOT_DETECTED"
      ? "No clear front-facing portrait was detected."
      : "The uploaded file could not be verified automatically.");

    const whyItMatters = guide.whyNeeded;

    const howToFixIt = qualityStatus === "IMAGE_GLARE"
      ? "Turn flash OFF on your camera, lay the card flat, and shoot under natural daylight."
      : qualityStatus === "IMAGE_CROPPED"
      ? "Step back 6 inches to ensure all four corners and borders are inside the camera frame."
      : qualityStatus === "IMAGE_BLURRY"
      ? "Hold your phone steady or tap the screen to refocus before taking the photo."
      : guide.correctionExamples[0] || "Take a sharp photo in daylight showing all 4 corners.";

    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50/70 p-4 text-xs text-amber-950 space-y-3 animate-fadeIn">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0" />
            <h5 className="font-bold text-amber-950 text-sm">
              {guide.shortLabel} needs a clearer image
            </h5>
          </div>
          <span className="rounded-full bg-amber-200/80 text-amber-900 font-bold px-2 py-0.5 text-[10px]">
            Action needed
          </span>
        </div>

        <div className="space-y-2 rounded-lg bg-white/90 border border-amber-200/80 p-3">
          <div>
            <p className="font-bold text-amber-950">What we found:</p>
            <p className="text-amber-900">{whatIsWrong}</p>
          </div>

          <div>
            <p className="font-bold text-amber-950">Why this matters:</p>
            <p className="text-slate-600">{whyItMatters}</p>
          </div>

          <div>
            <p className="font-bold text-amber-950">How to fix it:</p>
            <p className="text-slate-700">{howToFixIt}</p>
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-amber-800 pt-1">
          <span>✓ Your previous upload is safely retained until you upload a better copy.</span>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          {onUploadBetterImage && (
            <button
              type="button"
              onClick={onUploadBetterImage}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-700 hover:bg-amber-800 text-white font-bold px-3 py-1.5 shadow-2xs text-xs"
            >
              <Upload className="h-3.5 w-3.5" /> Upload a better image
            </button>
          )}
          {onAskCopilot && (
            <button
              type="button"
              onClick={onAskCopilot}
              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white hover:bg-amber-50 text-amber-900 font-semibold px-3 py-1.5 text-xs"
            >
              <HelpCircle className="h-3.5 w-3.5" /> Ask Copilot why this was flagged
            </button>
          )}
        </div>
      </div>
    );
  }

  // 3. HUMAN REVIEW
  if (effectiveState === "HUMAN_REVIEW") {
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-4 text-xs text-sky-950 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-sky-700 shrink-0" />
            <h5 className="font-bold text-sky-950 text-sm">Sent to a reviewer</h5>
          </div>
          <span className="rounded-full bg-sky-100 text-sky-800 font-bold px-2 py-0.5 text-[10px]">
            In Review
          </span>
        </div>

        <p className="text-sky-900 leading-relaxed">
          This document type requires human confirmation per IRDAI guidelines (e.g. recognized state board, joint bank account, or maiden name variation).
        </p>

        <div className="rounded-lg bg-white/80 border border-sky-100 p-2.5 space-y-1 text-slate-600 text-[11px]">
          <p>• <strong>You do not need to do anything right now.</strong></p>
          <p>• A certified reviewer will check your document within 24–48 hours.</p>
          <p>• We will notify you via SMS and WhatsApp as soon as review is complete.</p>
        </div>
      </div>
    );
  }

  // 4. IN PROGRESS / READING
  if (effectiveState === "READING_DOCUMENT" || effectiveState === "UPLOADING" || effectiveState === "QUALITY_CHECK") {
    return (
      <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-3.5 text-xs text-indigo-950 space-y-2">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-indigo-600 animate-spin" />
          <span className="font-bold text-indigo-900">
            {effectiveState === "UPLOADING"
              ? "Encrypting and uploading file..."
              : effectiveState === "QUALITY_CHECK"
              ? "Running automated image quality heuristics..."
              : "Reading document fields securely..."}
          </span>
        </div>
        <p className="text-indigo-800 text-[11px]">
          Checking focus, lighting, and borders. This usually takes 2–4 seconds.
        </p>
      </div>
    );
  }

  return null;
}
