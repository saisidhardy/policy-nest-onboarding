"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import React, { useState } from "react";
import { DOCUMENT_GUIDANCE_MAP } from "@/lib/documentGuidance";
import type { ApplicationDocument, DocumentType } from "@/lib/types";

export interface KeepTheseReadyPanelProps {
  currentStep: number;
  documents?: ApplicationDocument[];
  onOpenPreparationGuide?: () => void;
  className?: string;
}

const DOC_ORDER: DocumentType[] = [
  "PAN_CARD",
  "AADHAAR_FRONT",
  "AADHAAR_BACK",
  "CLASS_10_MARKSHEET",
  "BANK_DOCUMENT",
  "APPLICANT_SELFIE",
];

export function KeepTheseReadyPanel({
  currentStep,
  documents = [],
  onOpenPreparationGuide,
  className,
}: KeepTheseReadyPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Map current uploaded documents
  const docMap = new Map<DocumentType, ApplicationDocument>();
  for (const doc of documents) {
    if (doc.is_current) {
      docMap.set(doc.doc_type, doc);
    }
  }

  const getItemState = (type: DocumentType) => {
    const doc = docMap.get(type);
    if (!doc) {
      if (currentStep === 5) {
        return {
          label: "Ready to upload",
          tone: "neutral" as const,
          icon: FileText,
          iconClass: "text-slate-400",
        };
      }
      return {
        label: "Needed in Step 5",
        tone: "neutral" as const,
        icon: FileText,
        iconClass: "text-slate-400",
      };
    }

    const st = doc.status?.toUpperCase() || "";
    if (st === "VERIFIED" || st === "VALIDATED") {
      return {
        label: "Verified automatically",
        tone: "success" as const,
        icon: CheckCircle2,
        iconClass: "text-emerald-600",
      };
    }
    if (st === "NEEDS_MORE_INFO" || st === "CORRECTION_REQUIRED" || st === "REJECTED") {
      return {
        label: "Clearer image required",
        tone: "warning" as const,
        icon: AlertTriangle,
        iconClass: "text-amber-600",
      };
    }
    if (st === "IN_REVIEW" || st === "HUMAN_REVIEW") {
      return {
        label: "Reviewer checking",
        tone: "brand" as const,
        icon: ShieldCheck,
        iconClass: "text-sky-600",
      };
    }
    return {
      label: "Uploaded — processing",
      tone: "brand" as const,
      icon: CheckCircle2,
      iconClass: "text-indigo-600",
    };
  };

  const completedCount = documents.filter((d) => d.is_current).length;

  return (
    <div
      className={clsx(
        "rounded-2xl border border-slate-200 bg-white shadow-2xs transition-all",
        className
      )}
      aria-label="Keep these ready side panel"
    >
      <div className="flex items-center justify-between p-3.5 sm:p-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Keep these ready</h3>
            <p className="text-[11px] text-slate-500">
              {completedCount} of 6 documents uploaded
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
          aria-expanded={!isCollapsed}
          aria-label={isCollapsed ? "Expand readiness panel" : "Collapse readiness panel"}
        >
          {isCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
        </button>
      </div>

      {!isCollapsed && (
        <div className="p-3 sm:p-4 space-y-2 text-xs">
          <div className="space-y-1.5">
            {DOC_ORDER.map((type) => {
              const guide = DOCUMENT_GUIDANCE_MAP[type];
              const st = getItemState(type);
              const Icon = st.icon;

              return (
                <div
                  key={type}
                  className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-slate-50 transition"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Icon className={clsx("h-3.5 w-3.5 shrink-0", st.iconClass)} />
                    <span className="truncate font-medium text-slate-800">
                      {guide.shortLabel}
                    </span>
                  </div>
                  <span
                    className={clsx(
                      "text-[11px] font-semibold shrink-0 ml-2",
                      st.tone === "success"
                        ? "text-emerald-700"
                        : st.tone === "warning"
                        ? "text-amber-700"
                        : st.tone === "brand"
                        ? "text-sky-700"
                        : "text-slate-500"
                    )}
                  >
                    {st.label}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="pt-3 border-t border-slate-100 flex flex-col gap-1.5 text-[11px]">
            {onOpenPreparationGuide && (
              <button
                type="button"
                onClick={onOpenPreparationGuide}
                className="w-full text-center py-1.5 rounded-lg border border-slate-200 bg-slate-50 font-semibold text-slate-700 hover:bg-slate-100 transition"
              >
                View preparation guide
              </button>
            )}
            <p className="text-[10px] text-slate-500 text-center">
              🔒 Encrypted AES-256 cloud storage · Aadhaar masked
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
